import tomlkit
from pathlib import Path
from typing import Dict

from rich import print

from posit_bakery.parser.filters import render_template


class TargetBuild:
    def __init__(self, manifest_name: str, build: Dict, target: Dict, manifest_path: Path, const: Dict = None):
        if const is None:
            const = {}

        self.image_name = const.get("image_name", manifest_name)
        self.build_data = build
        self.target_data = target

        self.version = build["version"]
        self.type = target["type"]

        # Resolve a unique name to be used in Bake plans
        self.name = f"{manifest_name}-{self.version}-{self.type}".replace(".", "-").replace("/", "-")

        self.latest = build.get("latest", False)

        # Resolve operating system type either via build array (product) or constants (base)
        self.os = None
        default_tags = ["{{ build.version }}"]
        default_latest_tags = []
        if self.build_data.get("os"):
            self.os = self.build_data["os"]
            self.containerfile_name = render_template(
                build.get("containerfile", "Containerfile.{{ build.os | condense }}.{{ target.type }}"),
                build=build,
                target=target,
                **const,
            )
            self.containerfile_path = manifest_path / self.version / self.containerfile_name

            if self.type == "std":
                default_tags = [
                    "{{ build.version | tag_safe }}-{{ build.os | condense }}",
                    "{{ build.version | clean_version }}-{{ build.os | condense }}",
                ]
                if self.latest:
                    default_latest_tags.append("{{ build.os | condense }}")
                    if self.build_data.get("primary_os"):
                        default_latest_tags.append("latest")
            else:
                default_tags = ["{{ build.version }}-{{ target.type }}"]
                if self.latest:
                    default_latest_tags = ["{{ build.os | condense }}-{{ target.type }}"]
                    if self.build_data.get("primary_os"):
                        default_latest_tags.append("latest-{{ target.type }}")
        elif const.get("os"):
            self.os = f"{const['os'].title()} {self.version}"
            self.containerfile_name = render_template(
                build.get("containerfile", f"Containerfile.{self.type}"), build=build, target=target, **const
            )
            self.containerfile_path = manifest_path / self.version / self.containerfile_name

            if self.type == "std":
                default_tags = ["{{ os | lower }}{{ build.version | condense }}"]
                if self.latest:
                    default_latest_tags = ["{{ os | lower }}{{ build.version | condense }}-latest"]
            else:
                default_tags = ["{{ build.version }}-{{ target.type }}"]
                if self.latest:
                    default_latest_tags = ["latest-{{ target.type }}"]
        else:
            print(
                f"[bright_yellow][bold]WARNING:[/bold] No operating system could be determined for manifest {self.name}."
                f" This can result in unexpected behavior."
            )

        # Render tags
        self.tags = []
        tag_list = target.get("tags", default_tags)
        for tag in tag_list:
            self.tags.append(render_template(tag, build=build, target=target, **const))
        if self.latest:
            for tag in target.get("latest_tags", default_latest_tags):
                self.tags.append(render_template(tag, build=build, target=target, **const))

        # Render Goss settings or set to defaults
        goss_data = target.get("goss")
        if goss_data:
            self.goss_deps = Path(
                render_template(goss_data.get("deps", f"{self.version}/deps"), build=build, target=target, **const)
            )
            self.goss_deps = manifest_path / self.goss_deps

            self.goss_test_path = Path(
                render_template(goss_data.get("path", f"{self.version}/test"), build=build, target=target, **const)
            )
            self.goss_test_path = manifest_path / self.goss_test_path

            self.goss_wait = goss_data.get("wait", 0)

            self.goss_command = render_template(
                goss_data.get("command", "sleep infinity"), build=build, target=target, **const
            )
        else:
            self.goss_deps = manifest_path / f"{self.version}/deps"
            self.goss_test_path = manifest_path / f"{self.version}/test"
            self.goss_wait = 0
            self.goss_command = "sleep infinity"

    def render_fq_tags(self, host_url: str):
        return [f"{host_url}/{self.image_name}:{tag}" for tag in self.tags]


class Manifest:
    def __init__(self, context: Path, name: str, manifest_file: Path, filters: Dict[str, str] = None):
        if filters is None:
            filters = {}
        self.name = name
        self.manifest_file = manifest_file
        self.manifest_file_relative = manifest_file.relative_to(context)
        self.load_manifest(manifest_file)
        self.const = self.manifest_config.get("const", {})
        self.targets_data = self.get_targets()
        self.builds_data = self.get_builds()
        self.target_builds = []
        for build in self.builds_data.values():
            for target_type, target in self.targets_data.items():
                build_targets = build.get("targets", [])
                if (target_type in build_targets or not build_targets) and (
                    filters.get("image_version") == build["version"] or filters.get("image_version") is None
                ):
                    self.target_builds.append(
                        TargetBuild(self.name, build, target, self.manifest_file_relative.parent, self.const)
                    )
                else:
                    print(f"[bright_black]Skipping target '{target_type}' for build version '{build['version']}'")

    def load_manifest(self, manifest_file: Path):
        with open(manifest_file, "rb") as f:
            self.manifest_config = tomlkit.load(f)

    def get_targets(self):
        targets = {}
        for target in self.manifest_config["target"]:
            targets[target["type"]] = target
        return targets

    def get_builds(self):
        builds = {}
        for build in self.manifest_config["build"]:
            if "os" in build:
                os_list = build["os"].copy()
                primary_os = os_list[0]
                for os in os_list:
                    build["os"] = os
                    build["primary_os"] = os == primary_os
                    builds[build["version"] + "-" + os] = build
            else:
                builds[build["version"]] = build
        return builds

    @classmethod
    def load_manifests_from_context(cls, context: Path, image_name: str = None, image_version: str = None):
        manifests = {}
        for manifest_file in context.rglob("manifest.toml"):
            manifest_name = str(manifest_file.parent.relative_to(context))
            if image_name and image_name != manifest_name:
                continue
            manifests[manifest_name] = cls(context, manifest_name, manifest_file, {"image_version": image_version})
        return manifests
