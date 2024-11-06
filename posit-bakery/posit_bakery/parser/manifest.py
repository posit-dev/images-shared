import os
import re

import tomlkit
from pathlib import Path
from typing import Dict, Union, List, Any

from rich import print
from tomlkit import TOMLDocument
from tomlkit.items import AoT, Table

from posit_bakery.parser.templating.filters import render_template


class TargetBuild:
    def __init__(
            self,
            manifest_name: str,
            build: Union[Table, Dict[str, Any]],
            target: Union[Table, Dict[str, Any]],
            manifest_path: Union[str, bytes, os.PathLike],
            const: Union[Table, Dict[str, Any]] = None
    ):
        # Default const to an empty dictionary
        if const is None:
            const = {}

        # Resolve image name
        self.image_name: str = const.get("image_name", manifest_name)

        # Save build and target data
        self.build_data: Union[Table, Dict[str, Any]] = build
        self.target_data: Union[Table, Dict[str, Any]] = target

        self.version: str = build["version"]
        self.type: str = target["type"]

        # Resolve a unique name to be used in Bake plans
        self.name: str = re.sub("[.+/]", "-", f"{manifest_name}-{self.version}-{self.type}")

        self.latest: bool = build.get("latest", False)

        # Resolve operating system type either via build array (product) or constants (base)
        self.os = None
        default_tags = ["{{ build.version }}"]
        default_latest_tags = []
        # Logic branch for product builds where OSes are non-homogenous
        if self.build_data.get("os"):
            self.os: str = self.build_data["os"]
            self.containerfile_name: str = render_template(
                build.get("containerfile", "Containerfile.{{ build.os | condense }}.{{ target.type }}"),
                build=build,
                target=target,
                **const,
            )
            self.containerfile_path: Path = Path(manifest_path) / self.version / self.containerfile_name

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
                default_tags = [
                    "{{ build.version | tag_safe }}-{{ build.os | condense }}-{{ target.type }}",
                    "{{ build.version | clean_version }}-{{ build.os | condense }}-{{ target.type }}",
                ]
                if self.latest:
                    default_latest_tags = ["{{ build.os | condense }}-{{ target.type }}"]
                    if self.build_data.get("primary_os"):
                        default_latest_tags.append("latest-{{ target.type }}")
        # Logic for base images where OS is homogenous
        elif const.get("os"):
            self.os: str = f"{const['os'].title()} {self.version}"
            self.containerfile_name: str = render_template(
                build.get("containerfile", f"Containerfile.{self.type}"), build=build, target=target, **const
            )
            self.containerfile_path: Path = Path(manifest_path) / self.version / self.containerfile_name

            if self.type == "std":
                default_tags = ["{{ os | lower }}{{ build.version | condense }}"]
                if self.latest:
                    default_latest_tags = ["{{ os | lower }}{{ build.version | condense }}-latest"]
            else:
                default_tags = ["{{ build.version }}-{{ target.type }}"]
                if self.latest:
                    default_latest_tags = ["latest-{{ target.type }}"]
        # The "best effort" path where no OS is defined
        else:
            print(
                f"[bright_yellow][bold]WARNING:[/bold] No operating system could be determined for manifest {self.name}."
                f" This can result in unexpected behavior."
            )

        # Render tags
        self.tags: List[str] = []
        tag_list = target.get("tags", default_tags)
        for tag in tag_list:
            self.tags.append(render_template(tag, build=build, target=target, **const))
        if self.latest:
            for tag in target.get("latest_tags", default_latest_tags):
                self.tags.append(render_template(tag, build=build, target=target, **const))

        # Render Goss settings or set to defaults
        goss_data = target.get("goss")
        if goss_data:
            self.goss_deps: Path = Path(
                render_template(goss_data.get("deps", f"{self.version}/deps"), build=build, target=target, **const)
            )
            self.goss_deps: Path = Path(manifest_path) / self.goss_deps

            self.goss_test_path: Path = Path(
                render_template(goss_data.get("path", f"{self.version}/test"), build=build, target=target, **const)
            )
            self.goss_test_path: Path = Path(manifest_path) / self.goss_test_path

            self.goss_wait: int = int(goss_data.get("wait", 0))

            self.goss_command: str = render_template(
                goss_data.get("command", "sleep infinity"), build=build, target=target, **const
            )
        else:
            self.goss_deps: Path = Path(manifest_path) / f"{self.version}/deps"
            self.goss_test_path: Path = Path(manifest_path) / f"{self.version}/test"
            self.goss_wait: int = 0
            self.goss_command: str = "sleep infinity"

    def render_fq_tags(self, host_url: str) -> List[str]:
        """Renders the fully qualified tags for the target build"""
        return [f"{host_url}/{self.image_name}:{tag}" for tag in self.tags]


class Manifest:
    def __init__(
            self,
            context: Union[str, bytes, os.PathLike],
            name: str,
            manifest_file: Union[str, bytes, os.PathLike],
            filters: Dict[str, str] = None,
    ):
        # Default filters to an empty dictionary
        if filters is None:
            filters = {}

        # Set manifest name and load manifest file
        self.name: str = name
        self.manifest_file: Path = Path(manifest_file)
        self.manifest_file_relative: Path = self.manifest_file.relative_to(Path(context))
        self.manifest_config: TOMLDocument = self.load(self.manifest_file)

        # Load manifest data
        # Get constants from the manifest or default to empty dictionary
        self.const: Union[Table, Dict[str, Any]] = self.manifest_config.get("const", {})
        # Load target and build data structures
        self.targets_data: Dict[str, Dict[str, Any]] = self.get_targets()
        self.builds_data: Dict[str, Dict[str, Any]] = self.get_builds()
        # Initialize list of target builds
        self.target_builds: List[TargetBuild] = []
        for build in self.builds_data.values():
            for target_type, target in self.targets_data.items():
                # Pair targets and builds together into TargetBuild objects
                build_targets = build.get("targets", [])
                if (target_type in build_targets or not build_targets) and (
                    filters.get("image_version") == build["version"] or filters.get("image_version") is None
                ):
                    # Add target if it matches the build's target list or the build does not have a target list
                    # AND the build is not filtered out by a version filter
                    self.target_builds.append(
                        TargetBuild(self.name, build, target, self.manifest_file_relative.parent, self.const)
                    )
                else:
                    print(f"[bright_black]Skipping target '{target_type}' for build version '{build['version']}'")

    @staticmethod
    def load(manifest_file: Union[str, bytes, os.PathLike]) -> TOMLDocument:
        """Loads a TOML file into a TOMLDocument object"""
        with open(manifest_file, "rb") as f:
            return tomlkit.load(f)

    def get_targets(self) -> Dict[str, Dict[str, Any]]:
        """Returns a dictionary of target types and their configurations"""
        targets = {}
        for target in self.manifest_config["target"]:
            targets[target["type"]] = target
        return targets

    def get_builds(self) -> Dict[str, Dict[str, Any]]:
        """Returns a dictionary of build versions and their configurations"""
        builds = {}
        for build in self.manifest_config["build"]:
            if "os" in build:
                os_list = build["os"].copy()
                primary_os = os_list[0]
                for _os in os_list:
                    build["os"] = _os
                    build["primary_os"] = _os == primary_os
                    builds[build["version"] + "-" + _os] = build
            else:
                builds[build["version"]] = build
        return builds

    @classmethod
    def load_manifests_from_context(
            cls, context: Union[str, bytes, os.PathLike], image_name: str = None, image_version: str = None
    ) -> Dict[str, "Manifest"]:
        """Loads all manifests from a context directory

        :param context: The context directory
        :param image_name: Filter the manifests loaded by image name
        :param image_version: Filter the manifests loaded by image version
        """
        manifests = {}
        context = Path(context)
        for manifest_file in context.rglob("manifest.toml"):
            manifest_name = str(manifest_file.parent.relative_to(context))
            if image_name and image_name != manifest_name:
                continue
            manifests[manifest_name] = cls(
                context, manifest_name, manifest_file, {"image_version": image_version}
            )
        return manifests
