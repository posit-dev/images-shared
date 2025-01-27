import logging
import os
import subprocess
from pathlib import Path
from typing import Union, List, Dict, Any, Tuple

import jinja2
from pydantic import BaseModel

from posit_bakery.error import (
    BakeryFileNotFoundError,
    BakeryBuildError,
    BakeryGossError,
    BakeryConfigError,
    BakeryTemplatingError,
)
from posit_bakery.models import Image, Config, Manifest
from posit_bakery.models.project.bake import BakePlan
from posit_bakery.models.project.image import Images, ImageFilter
from posit_bakery.templating import TPL_CONFIG_TOML, TPL_MANIFEST_TOML, TPL_CONTAINERFILE
import posit_bakery.util as util


log = logging.getLogger("rich")


class Project(BaseModel):
    context: Path = None
    config: Config = None
    manifests: Dict[str, Manifest] = {}
    images: Dict[str, Image] = {}

    # TODO: Add back in support for handling overrides
    @classmethod
    def load(cls, context: Union[str, bytes, os.PathLike]) -> "Project":
        """Create a Project object and load config and manifests into it from a context directory

        :param context: The path to the context directory
        :param ignore_override: If true, ignores config.override.toml if it exists
        """
        project = cls()
        project.context = Path(context)
        if not project.context.is_dir():
            raise BakeryFileNotFoundError(f"Directory {project.context} does not exist.")
        project.config = project.load_config(project.context)
        project.manifests = project.load_manifests(project.config)
        project.images = project.load_images(project.manifests)

        return project

    @staticmethod
    def load_config(context: Union[str, bytes, os.PathLike]) -> Config:
        """Load the project configuration from a context directory

        :param context: The path to the context directory
        """
        context = Path(context)
        if not context.is_dir():
            raise BakeryFileNotFoundError(f"Directory {context} does not exist.")
        config_filepath = context / "config.toml"
        if not config_filepath.is_file():
            raise BakeryFileNotFoundError(f"Config file {config_filepath} does not exist.")
        config = Config.load(config_filepath)

        return config

    @staticmethod
    def load_manifests(config: Config) -> Dict[str, "Manifest"]:
        """Loads all manifests from a context directory

        :param config: The project configuration
        """
        manifests = {}
        for manifest_file in config.context.rglob("manifest.toml"):
            m = Manifest.load(manifest_file)
            if m.image_name in manifests:
                raise BakeryConfigError(f"Image name {m.name} shadows another image name in this project.")
            manifests[m.image_name] = m

        return manifests

    @staticmethod
    def load_images(manifests: Dict[str, Manifest]) -> Images:
        """Loads all images from the context directory"""
        return Images.load(manifests)

    def new_image(self, image_name: str, base_tag: str = "docker.io/library/ubuntu:22.04"):
        """Create a new image in the project with associated file structure from templates

        :param image_name: The name of the new image
        :param base_tag: The base tag to use for the new image
        """
        if image_name in self.manifests:
            raise BakeryConfigError(f"Image name {image_name} already exists in this project.")

        config_file = self.context / "config.toml"
        if not config_file.is_file():
            log.info(f"[bright_black]Creating new project config file [bold]{config_file}")
            tpl = jinja2.Environment(loader=jinja2.FileSystemLoader(self.context)).from_string(TPL_CONFIG_TOML)
            rendered = tpl.render(repo_url=util.try_get_repo_url(self.context))
            with open(config_file, "w") as f:
                f.write(rendered)

        image_path = self.context / image_name
        if not image_path.is_dir():
            log.info(f"[bright_black]Creating new image directory [bold]{image_path}")
            image_path.mkdir()

        manifest_file = image_path / "manifest.toml"
        if manifest_file.is_file():
            log.error(f"Manifest file [bold]{manifest_file}[/bold] already exists")
            raise BakeryTemplatingError(f"Manifest file '{manifest_file}' already exists. Please remove it first.")
        else:
            log.info(f"[bright_black]Creating new manifest file [bold]{manifest_file}")
            tpl = jinja2.Environment().from_string(TPL_MANIFEST_TOML)
            rendered = tpl.render(image_name=image_name)
            with open(manifest_file, "w") as f:
                f.write(rendered)

        image_template_path = image_path / "template"
        if not image_template_path.is_dir():
            log.info(f"[bright_black]Creating new image templates directory [bold]{image_template_path}")
            image_template_path.mkdir()

        # Create a new Containerfile template if it doesn't exist
        containerfile_path = image_template_path / "Containerfile.jinja2"
        if not containerfile_path.is_file():
            log.info(f"[bright_black]Creating new Containerfile template [bold]{containerfile_path}")
            tpl = jinja2.Environment().from_string(TPL_CONTAINERFILE)
            rendered = tpl.render(image_name=image_name, base_tag=base_tag)
            with open(containerfile_path, "w") as f:
                f.write(rendered)

        image_test_path = image_template_path / "test"
        if not image_test_path.is_dir():
            log.info(f"[bright_black]Creating new image templates test directory [bold]{image_test_path}")
            image_test_path.mkdir()
        image_test_goss_file = image_test_path / "goss.yaml.jinja2"
        image_test_goss_file.touch(exist_ok=True)

        image_deps_path = image_template_path / "deps"
        if not image_deps_path.is_dir():
            log.info(f"[bright_black]Creating new image templates dependencies directory [bold]{image_deps_path}")
            image_deps_path.mkdir()
        image_deps_package_file = image_deps_path / "packages.txt.jinja2"
        image_deps_package_file.touch(exist_ok=True)

    def new_image_version(
        self,
        image_name: str,
        image_version: str,
        value_map: Dict[str, str] = None,
        mark_latest: bool = True,
        save: bool = True,
    ):
        """Create a new version of an image in the project, render templates, and add it to the manifest

        :param image_name: The name of the image to create a new version for
        :param image_version: The new version
        :param value_map: A dictionary of key/values to use in template rendering
        :param mark_latest: If true, mark the new version as the latest
        :param save: If true, save to the manifest.toml after adding the new version
        """
        if image_name not in self.manifests:
            raise BakeryConfigError(f"Image name {image_name} does not exist in this project.")
        if value_map is None:
            value_map = {}
        manifest = self.manifests[image_name]
        manifest.new_version(image_version, mark_latest=mark_latest, value_map=value_map, save=save)

    def render_bake_plan(
        self,
        image_name: str = None,
        image_version: str = None,
        image_type: str = None,
    ) -> Dict[str, Any]:
        """Render a bake plan for the project

        :param image_name: (Optional) The name of the image to render a bake plan for
        :param image_version: (Optional) The version of the image to render a bake plan for
        :param image_type: (Optional) The type of the image to render a bake plan for
        """
        filter: ImageFilter = ImageFilter(
            image_name=image_name,
            image_version=image_version,
            target_type=image_type,
        )
        selected_images = self.images.filter(filter)
        return BakePlan.create(config=self.config.model, images=selected_images.values())

    def build(
        self,
        load: bool = False,
        push: bool = False,
        image_name: str = None,
        image_version: str = None,
        image_type: str = None,
        build_options: List[str] = None,
    ) -> None:
        """Build images in the project using Buildkit Bake

        :param load: If true, load the built images into the local Docker daemon
        :param push: If true, push the built images to the registry
        :param image_name: (Optional) The name of the image to build
        :param image_version: (Optional) The version of the image to build
        :param image_type: (Optional) The type of the image to build
        :param build_options: (Optional) Additional build options to pass to `docker buildx bake` command
        """
        bake_plan = self.render_bake_plan(image_name, image_version, image_type)
        build_file = self.context / ".docker-bake.json"
        with open(build_file, "w") as f:
            f.write(bake_plan.model_dump_json(indent=2))

        cmd = ["docker", "buildx", "bake", "--file", str(build_file)]
        if load:
            cmd.append("--load")
        if push:
            cmd.append("--push")
        if build_options:
            cmd.extend(build_options)
        run_env = os.environ.copy()
        log.info(f"[bright_black]Executing build command: {' '.join(cmd)}")
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
    ) -> List[Tuple[str, Dict[str, str], List[str]]]:
        """Render dgoss commands for the project

        :param image_name: (Optional) The name of the image to render dgoss commands for
        :param image_version: (Optional) The version of the image to render dgoss commands for
        :param image_type: (Optional) The type of the image to render dgoss commands for
        :param runtime_options: (Optional) Additional runtime options to pass to the dgoss command
        """
        dgoss_bin = util.find_bin(self.context, "dgoss", "DGOSS_PATH") or "dgoss"
        goss_bin = util.find_bin(self.context, "goss", "GOSS_PATH")
        dgoss_commands = []

        images: Images = self.images.filter(
            ImageFilter(image_name=image_name, image_version=image_version, target_type=image_type)
        )

        for variant in images.variants:
            run_env = os.environ.copy()
            cmd = [dgoss_bin, "run"]

            if goss_bin is not None:
                run_env["GOSS_PATH"] = goss_bin

            test_path = variant.goss.tests
            if test_path is None or test_path == "":
                raise BakeryGossError(
                    "Path to Goss test directory must be defined or left empty for default. Please check the manifest.toml."
                )
            run_env["GOSS_FILES_PATH"] = str(test_path)

            deps = variant.goss.deps
            if deps.is_dir():
                cmd.append(f"--mount=type=bind,source={str(deps)},destination=/tmp/deps")
            else:
                log.warning(f"Skipping mounting of goss deps directory {deps} as it does not exist.")

            if variant.goss.wait is not None and variant.goss.wait > 0:
                run_env["GOSS_SLEEP"] = str(variant.goss.wait)

            # Check if build type is defined and set the image typez
            if variant.target is not None:
                cmd.extend(["-e", f"IMAGE_TYPE={variant.target}"])

            # Add user runtime options if provided
            if runtime_options:
                cmd.extend(runtime_options)

            # Append the target image tag, assuming the first one is valid to use and no duplications exist
            cmd.append(variant.tags[0])

            # Append the goss command to run or use the default `sleep infinity`
            cmd.extend(variant.goss.command.split() or ["sleep", "infinity"])

            dgoss_commands.append((variant.tags[0], run_env, cmd))
        # dgoss_commands.sort(key=lambda x: x[0])

        return dgoss_commands

    def dgoss(
        self,
        image_name: str = None,
        image_version: str = None,
        image_type: str = None,
        runtime_options: List[str] = None,
    ) -> None:
        """Run Goss tests for the project's images using dgoss

        :param image_name: (Optional) The name of the image to run Goss tests for
        :param image_version: (Optional) The version of the image to run Goss tests for
        :param image_type: (Optional) The type of the image to run Goss tests for
        :param runtime_options: (Optional) Additional runtime options to pass to the dgoss command
        """
        dgoss_commands = self.render_dgoss_commands(image_name, image_version, image_type, runtime_options)
        for tag, env, cmd in dgoss_commands:
            log.info(f"[bright_blue bold]=== Running Goss tests for {tag} ===")
            log.info(f"[bright_black]Executing dgoss command: {' '.join(cmd)}")
            p = subprocess.run(cmd, env=env, cwd=self.context)
            if p.returncode != 0:
                raise BakeryGossError(f"Goss exited with code {p.returncode}", p.returncode)
            log.info(f"[bright_green bold]=== Goss tests passed for {tag} ===")
