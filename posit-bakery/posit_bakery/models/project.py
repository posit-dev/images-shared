import json
import os
import subprocess
from pathlib import Path
from shutil import which
from typing import Union, List, Dict, Any, Tuple

import git
import jinja2

from posit_bakery.error import BakeryFileNotFoundError, BakeryBuildError, BakeryGossError, BakeryConfigError, \
    BakeryTemplatingError
from posit_bakery.models.config import Config
from posit_bakery.models.manifest import Manifest

from posit_bakery.templating.templates.configuration import TPL_CONFIG_TOML, TPL_MANIFEST_TOML
from posit_bakery.templating.templates.containerfile import TPL_CONTAINERFILE


class Project:
    def __init__(self) -> None:
        self.context: Path = None
        self.config: Config = None
        self.manifests: Dict[str, "Manifest"] = {}

    @classmethod
    def from_context(cls, context: Union[str, bytes, os.PathLike], no_override: bool = False) -> "Project":
        project = cls()
        project.context = Path(context)
        if not project.context.exists():
            raise BakeryFileNotFoundError(f"Directory {project.context} does not exist.")
        project.config = project.__load_context_config(project.context, no_override)
        project.manifests = project.__load_config_manifests(project.config)
        return project

    def __find_bin(self, bin_name: str, bin_env_var: str):
        if bin_env_var in os.environ:
            return os.environ[bin_env_var]
        elif which(bin_name) is not None:
            return None
        elif (self.context / "tools" / bin_name).exists():
            return str(self.context / "tools" / bin_name)
        else:
            raise BakeryFileNotFoundError(
                f"Could not find {bin_name} in PATH or in project tools directory. "
                f"Either install {bin_name} or set the `{bin_env_var}` environment variable."
            )

    @staticmethod
    def __load_context_config(context: Union[str, bytes, os.PathLike], no_override: bool = False) -> Config:
        context = Path(context)
        if not context.exists():
            raise BakeryFileNotFoundError(f"Directory {context} does not exist.")
        config_filepath = context / "config.toml"
        if not config_filepath.exists():
            raise BakeryFileNotFoundError(f"Config file {config_filepath} does not exist.")
        config = Config.load_file(config_filepath)

        override_config_filepath = context / "config.override.toml"
        if not no_override and override_config_filepath.exists():
            override_config = Config.load_file(override_config_filepath)
            config.merge(override_config)

        return config

    @staticmethod
    def __load_config_manifests(config: Config) -> Dict[str, "Manifest"]:
        """Loads all manifests from a context directory

        :param config: The project configuration
        """
        manifests = {}
        for manifest_file in config.context.rglob("manifest.toml"):
            m = Manifest.load_file_with_config(config, manifest_file)
            if m.image_name in manifests:
                raise ValueError(f"Image name {m.name} shadows another image name in this project.")
            manifests[m.image_name] = m
        return manifests

    def new_image(self, image_name: str, base_tag: str = "docker.io/library/ubuntu:22.04"):
        if image_name in self.manifests:
            raise BakeryConfigError(f"Image name {image_name} already exists in this project.")

        config_file = self.context / "config.toml"
        if not config_file.exists():
            print(f"[bright_black]Creating new project config file [bold]{config_file}")
            tpl = jinja2.Environment(loader=jinja2.FileSystemLoader(self.context)).from_string(TPL_CONFIG_TOML)
            rendered = tpl.render(repo_url=try_get_repo_url(self.context))
            with open(config_file, "w") as f:
                f.write(rendered)

        image_path = self.context / image_name
        if not image_path.exists():
            print(f"[bright_black]Creating new image directory [bold]{image_path}")
            image_path.mkdir()

        manifest_file = image_path / "manifest.toml"
        if manifest_file.exists():
            print(f"[bright_red bold]ERROR:[/bold] Manifest file [bold]{manifest_file}[/bold] already exists")
            raise BakeryTemplatingError(f"Manifest file '{manifest_file}' already exists. Please remove it first.")
        else:
            print(f"[bright_black]Creating new manifest file [bold]{manifest_file}")
            tpl = jinja2.Environment().from_string(TPL_MANIFEST_TOML)
            rendered = tpl.render(image_name=image_name)
            with open(manifest_file, "w") as f:
                f.write(rendered)

        image_template_path = image_path / "template"
        if not image_template_path.exists():
            print(f"[bright_black]Creating new image templates directory [bold]{image_template_path}")
            image_template_path.mkdir()

        # Create a new Containerfile template if it doesn't exist
        containerfile_path = image_template_path / "Containerfile.jinja2"
        if not containerfile_path.exists():
            print(f"[bright_black]Creating new Containerfile template [bold]{containerfile_path}")
            tpl = jinja2.Environment().from_string(TPL_CONTAINERFILE)
            rendered = tpl.render(image_name=image_name, base_tag=base_tag)
            with open(containerfile_path, "w") as f:
                f.write(rendered)

        image_test_path = image_template_path / "test"
        if not image_test_path.exists():
            print(f"[bright_black]Creating new image templates test directory [bold]{image_test_path}")
            image_test_path.mkdir()
        image_test_goss_file = image_test_path / "goss.yaml.jinja2"
        image_test_goss_file.touch(exist_ok=True)

        image_deps_path = image_template_path / "deps"
        if not image_deps_path.exists():
            print(f"[bright_black]Creating new image templates dependencies directory [bold]{image_deps_path}")
            image_deps_path.mkdir()
        image_deps_package_file = image_deps_path / "packages.txt.jinja2"
        image_deps_package_file.touch(exist_ok=True)

    def new_image_version(
            self, image_name: str, image_version: str, value_map: Dict[str, str], mark_latest: bool = True
    ):
        if image_name not in self.manifests:
            raise BakeryConfigError(f"Image name {image_name} does not exist in this project.")
        manifest = self.manifests[image_name]
        manifest.new_version(image_version, mark_latest, value_map)

    def render_bake_plan(
            self,
            image_name: str = None,
            image_version: str = None,
            image_type: str = None,
    ) -> Dict[str, Any]:
        bake_plan = {
            "group": {"default": {"targets": []}},
            "target": {},
        }

        for manifest in self.manifests.values():
            if image_name and manifest.image_name != image_name:
                continue

            if manifest.image_name not in bake_plan["group"]:
                bake_plan["group"][manifest.image_name] = {"targets": []}

            for target_build in manifest.target_builds:
                if image_version and target_build.version != image_version:
                    continue
                if image_type and target_build.type != image_type:
                    continue

                if target_build.type not in bake_plan["group"]:
                    bake_plan["group"][target_build.type] = {"targets": []}

                target_definition = {
                    "context": ".",
                    "dockerfile": target_build.containerfile,
                    "labels": target_build.labels,
                    "tags": target_build.all_tags,
                }
                bake_plan["target"][target_build.uid] = target_definition
                bake_plan["group"]["default"]["targets"].append(target_build.uid)
                bake_plan["group"][manifest.image_name]["targets"].append(target_build.uid)
                bake_plan["group"][target_build.type]["targets"].append(target_build.uid)
        return bake_plan

    def build(
            self,
            load: bool = False,
            push: bool = False,
            image_name: str = None,
            image_version: str = None,
            image_type: str = None,
            build_options: List[str] = None,
    ) -> None:
        bake_plan = self.render_bake_plan(image_name, image_version, image_type)
        build_file = self.context / ".docker-bake.json"
        with open(build_file, "w") as f:
            json.dump(bake_plan, f, indent=2)

        cmd = ["docker", "buildx", "build", "--file", str(build_file)]
        if load:
            cmd.append("--load")
        if push:
            cmd.append("--push")
        if build_options:
            cmd.extend(build_options)
        run_env = os.environ.copy()
        p = subprocess.run(cmd, env=run_env, cwd=self.context)
        if p.returncode != 0:
            raise BakeryBuildError(p.returncode)
        build_file.unlink()

    def render_dgoss_commands(
            self,
            image_name: str = None,
            image_version: str = None,
            image_type: str = None,
            runtime_options: List[str] = None,
        ) -> List[Tuple[Dict[str, str], List[str]]]:
        dgoss_bin = self.__find_bin("dgoss", "DGOSS_PATH") or "dgoss"
        goss_bin = self.__find_bin("goss", "GOSS_PATH")
        dgoss_commands = []

        for manifest in self.manifests.values():
            if image_name and manifest.image_name != image_name:
                continue

            for target_build in manifest.target_builds:
                if image_version and target_build.version != image_version:
                    continue
                if image_type and target_build.type != image_type:
                    continue

                run_env = os.environ.copy()
                cmd = [dgoss_bin, "run"]

                if goss_bin is not None:
                    run_env["GOSS_PATH"] = goss_bin

                test_path = target_build.goss.test_path
                if test_path is None or test_path == "":
                    raise BakeryGossError(
                        "Path to Goss test directory must be defined or left empty for default. Please check the manifest.toml."
                    )
                run_env["GOSS_FILES_PATH"] = str(test_path)

                deps = target_build.goss.deps
                if deps.exists():
                    cmd.append(f"--mount=type=bind,source={str(deps)},destination=/tmp/deps")
                else:
                    print(
                        f"[bright_yellow][bold]WARNING:[/bold] "
                        f"Skipping mounting of goss deps directory {deps} as it does not exist."
                    )

                if target_build.goss.wait is not None and target_build.goss.wait > 0:
                    run_env["GOSS_SLEEP"] = str(target_build.goss.wait)

                # Check if build type is defined and set the image type
                if target_build.type is not None:
                    cmd.extend(["-e", f"IMAGE_TYPE={target_build.type}"])

                # Add user runtime options if provided
                if runtime_options:
                    cmd.extend(runtime_options)

                # Append the target image tag, assuming the first one is valid to use and no duplications exist
                cmd.append(target_build.all_tags[0])

                # Append the goss command to run or use the default `sleep infinity`
                cmd.extend(target_build.goss.command.split() or ["sleep", "infinity"])

                dgoss_commands.append((run_env, cmd))

        return dgoss_commands

    def dgoss(
            self,
            image_name: str = None,
            image_version: str = None,
            image_type: str = None,
            runtime_options: List[str] = None,
        ) -> None:
        dgoss_commands = self.render_dgoss_commands(image_name, image_version, image_type, runtime_options)
        for env, cmd in dgoss_commands:
            p = subprocess.run(cmd, env=env, cwd=self.context)
            if p.returncode != 0:
                raise BakeryGossError(f"Goss exited with code {p.returncode}", p.returncode)


def try_get_repo_url(context: Union[str, bytes, os.PathLike]) -> str:
    """Best guesses a repository URL for image labeling purposes based off the Git remote origin URL

    :param context: The repository root to check for a remote URL in
    :return: The guessed repository URL
    """
    url = "<REPLACE ME>"
    try:
        repo = git.Repo(context)
        # Use splitext since remotes should have `.git` as a suffix
        url = os.path.splitext(repo.remotes[0].config_reader.get("url"))[0]
        # If the URL is a git@ SSH URL, convert it to a https:// URL
        if url.startswith("git@"):
            url = url.removeprefix("git@")
            url = url.replace(":", "/")
        # TODO: There should be more logic around HTTPS URLs that may use `user@` prefixing
    except:  # noqa
        print("[bright_yellow][bold]WARNING:[/bold] Unable to determine repository name ")
    return url
