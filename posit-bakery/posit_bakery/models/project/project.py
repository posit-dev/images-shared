import logging
import os
import subprocess
from pathlib import Path
from typing import Union, List, Dict, Tuple, Any

import pydantic
from pydantic import BaseModel

from posit_bakery.error import (
    BakeryImageError,
    BakeryImageNotFoundError,
    BakeryModelValidationError,
    BakeryToolRuntimeError,
    BakeryModelValidationErrorGroup, BakeryFileError,
)
from posit_bakery.models import Config, Manifest, Image, Images, ImageFilter
from posit_bakery.models.manifest import guess_os_list
from posit_bakery.models.project.bake import BakePlan
import posit_bakery.util as util


log = logging.getLogger(__name__)


class Project(BaseModel):
    context: Path = None
    config: Config = None
    manifests: Dict[str, Manifest] = {}
    images: Dict[str, Image] = {}

    @classmethod
    def create(cls, context: Union[str, bytes, os.PathLike]) -> "Project":
        """Create relevant files for a new project in a context directory

        :param context: The path to the context directory
        """
        project = cls()
        project.context = Path(context)

        if project.context.is_file():
            raise BakeryFileError(f"Given context '{project.context}' is a file.", project.context)
        if not project.context.exists():
            project.context.mkdir(parents=True)

        project.config = Config.create(project.context)

        # TODO: Consider anything else we should do here (e.g. .gitignore, init git, Justfile, etc.)

        return project

    @staticmethod
    def exists(context: Union[str, bytes, os.PathLike]) -> bool:
        """Check if a project exists in a context directory

        This checks essentially 2 things at the moment:
        - Does the given context exist as a directory?
        - Does the given context contain a config.toml file?

        :param context: The path to the context directory
        """
        project_context = Path(context)

        # Check if the context exists and is a directory
        if not project_context.exists():
            return False
        if project_context.is_file():
            raise BakeryFileError(f"Given context '{project_context}' is a file.", project_context)

        # Check if the context contains a config.toml file
        config_file = project_context / "config.toml"
        if not config_file.is_file():
            return False

        return True

    # TODO: Add back in support for handling overrides
    @classmethod
    def load(cls, context: Union[str, bytes, os.PathLike]) -> "Project":
        """Create a Project object and load config and manifests into it from a context directory

        :param context: The path to the context directory
        :param ignore_override: If true, ignores config.override.toml if it exists
        """
        project = cls()

        log.debug("Inspecting project context directory")
        project.context = Path(context)
        if not project.context.exists():
            log.error(f"Project context does not exist: {project.context}")
            raise BakeryFileError(f"Project context does not exist.", project.context)
        if not project.context.is_dir():
            log.error(f"Project context is not a directory: {project.context}")
            raise BakeryFileError(f"Project context is not a directory.", project.context)

        config_filepath = project.context / "config.toml"
        log.debug(f"Loading project config from {config_filepath}")
        if not config_filepath.is_file():
            log.error(f"Project config.toml file not found: {config_filepath}")
            raise BakeryFileError(f"Project config.toml file not found.", config_filepath)
        try:
            project.config = Config.load(config_filepath)
        except pydantic.ValidationError as e:
            log.error(f"Validation error occurred loading project config: {config_filepath}")
            raise BakeryModelValidationError(model_name="Config", filepath=config_filepath) from e

        log.debug("Loading project manifests")
        project.manifests = project.load_manifests(project.config)
        log.debug("Loading project images")
        project.images = Images.load(config=project.config, manifests=project.manifests)

        log.debug("Project loaded successfully")
        return project

    @staticmethod
    def load_manifests(config: Config) -> Dict[str, "Manifest"]:
        """Loads all manifests from a context directory

        :param config: The project configuration
        """
        # TODO: Consider implementing a Manifests dictionary class similar to Images
        manifests = {}
        error_list = []
        for manifest_file in config.context.rglob("manifest.toml"):
            try:
                log.debug(f"Loading manifest from {manifest_file}")
                m = Manifest.load(manifest_file)
            except pydantic.ValidationError as e:
                # TODO: Make this less goofy
                # This was the only obvious way I could find to chain the exception from the pydantic error and still
                # group it into the error_list for the BakeryModelValidationErrorGroup.
                log.error(f"Validation error occurred loading manifest: {manifest_file}")
                try:
                    raise BakeryModelValidationError(model_name="Manifest", filepath=manifest_file) from e
                except BakeryModelValidationError as e:
                    error_list.append(e)
                continue
            if m.image_name in manifests:
                log.error(f"Failed to load image, image name {m.name} shadows another image name in this project.")
                raise BakeryImageError(f"Image name {m.name} shadows another image name in this project.")
            manifests[m.image_name] = m

        if error_list:
            if len(error_list) == 1:
                raise error_list[0]
            raise BakeryModelValidationErrorGroup(
                "Multiple validation errors occurred while loading manifests.", error_list
            )

        log.debug(f"Loaded {len(manifests)} manifest(s) successfully")
        return manifests

    def create_image(self, image_name: str, base_tag: str):
        """Create a new image in the project with associated file structure from templates

        :param image_name: The name of the new image
        :param base_tag: The base tag to use for the new image
        """
        if image_name in self.manifests:
            log.error(f"Image '{image_name}' already exists in this project.")
            raise BakeryImageError(f"Image '{image_name}' already exists.")

        Image.create(project_context=self.context, name=image_name, base_tag=base_tag)
        # TODO: Do we update the project with a new manifest, or pick it up when we run bakery again?

    def create_image_version(
        self,
        image_name: str,
        image_version: str,
        template_values: Dict[str, Any] = None,
        mark_latest: bool = True,
        save: bool = True,
        force: bool = False,
    ):
        """Create a new version of an image in the project, render templates, and add it to the manifest

        :param image_name: The name of the image to create a new version for
        :param image_version: The new version
        :param template_values: A dictionary of key/values to use in template rendering
        :param mark_latest: If true, mark the new version as the latest
        :param save: If true, save to the manifest.toml after adding the new version
        :param force: If true, overwrite an existing version
        """
        log.info(f"Creating version '{image_version}' for image '{image_name}'.")
        if image_name not in self.manifests:
            log.error(f"Image '{image_name}' does not exist, cannot create version.")
            raise BakeryImageNotFoundError(f"Image '{image_name}' does not exist in this project.")

        image: Image = self.images[image_name]

        manifest: Manifest = self.manifests[image_name]
        if image_version in manifest.model.build:
            if not force:
                log.error(f"Version '{image_version}' already exists for image '{image_name}'.")
                raise BakeryImageError(f"Version '{image_version}' already exists for image '{image_name}'.")
            else:
                log.warning(f"Overwriting existing version '{image_version}' for image '{image_name}'.")

        new_version = image.create_version(
            manifest=manifest.model, version=image_version, template_values=template_values
        )

        if save:
            log.info(f"Adding version '{image_version}' to manifest.")
            os_list: List[str] = [_os.pretty for _os in guess_os_list(new_version.context)]
            manifest.add_version(image_version, os_list, mark_latest)

    def render_bake_plan(
        self,
        image_name: str = None,
        image_version: str = None,
        image_type: str = None,
    ) -> BakePlan:
        """Render a bake plan for the project

        :param image_name: (Optional) The name of the image to render a bake plan for
        :param image_version: (Optional) The version of the image to render a bake plan for
        :param image_type: (Optional) The type of the image to render a bake plan for
        """
        log.info("[bright_blue bold]Rendering bake plan...")
        _filter: ImageFilter = ImageFilter(
            image_name=image_name,
            image_version=image_version,
            target_type=image_type,
        )
        if _filter:
            return BakePlan.create(images=list(self.images.filter(_filter).values()))

        return BakePlan.create(images=list(self.images.values()))

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
        log.debug(f"[bright_black]Executing build command: {' '.join(cmd)}")
        log.info("[bright_blue bold]Starting image builds...")
        p = subprocess.run(cmd, env=run_env, cwd=self.context)
        if p.returncode != 0:
            log.error("Subprocess call to docker buildx bake failed.")
            raise BakeryToolRuntimeError(
                "Subprocess call to docker buildx bake failed.",
                "docker",
                cmd=cmd,
                stdout=p.stdout,
                stderr=p.stderr,
                exit_code=p.returncode,
            )
        build_file.unlink()
        log.info("[bright_blue bold]Builds completed.")

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

        filter: ImageFilter = ImageFilter(
            image_name=image_name,
            image_version=image_version,
            target_type=image_type,
        )
        images = self.images.filter(filter) if filter else self.images

        for variant in images.variants:
            run_env = os.environ.copy()
            cmd = [dgoss_bin, "run"]

            if goss_bin is not None:
                run_env["GOSS_PATH"] = goss_bin

            test_path = variant.goss.tests
            if test_path is None or test_path == "":
                raise BakeryFileError("Path to Goss test directory must be defined or left empty for default.")
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
        # TODO: implement "fail fast" behavior for dgoss where users can toggle to exit on the first failed test
        #       (current behavior) or perform all tests and summarize failures at the end.
        dgoss_commands = self.render_dgoss_commands(image_name, image_version, image_type, runtime_options)
        for tag, env, cmd in dgoss_commands:
            log.info(f"[bright_blue bold]=== Running Goss tests for {tag} ===")
            log.info(f"[bright_black]Executing dgoss command: {' '.join(cmd)}")
            p = subprocess.run(cmd, env=env, cwd=self.context)
            # TODO: Only print stdout and stderr on DEBUG log level, else suppress
            if p.returncode != 0:
                log.error(f"Subprocess call to dgoss exited with code {p.returncode}")
                raise BakeryToolRuntimeError(
                    f"Subprocess call to dgoss exited with code {p.returncode}",
                    "dgoss",
                    cmd=cmd,
                    stdout=p.stdout,
                    stderr=p.stderr,
                    exit_code=p.returncode,
                )
            log.info(f"[bright_green bold]=== Goss tests passed for {tag} ===")
