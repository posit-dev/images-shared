import json
import logging
import os
import shutil
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
    BakeryModelValidationErrorGroup,
    BakeryFileError, BakeryToolError, BakeryToolRuntimeErrorGroup,
)
from posit_bakery.models import Config, Manifest, Image, Images, ImageFilter
from posit_bakery.models.image.variant import ImageVariant
from posit_bakery.models.manifest import guess_os_list
from posit_bakery.models.manifest.snyk import SnykContainerSubcommand, get_exit_code_meaning
from posit_bakery.models.project.bake import BakePlan, target_uid
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

    def has_images(self):
        return True if len(self.images) > 0 else False

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
        if not self.has_images():
            raise BakeryImageNotFoundError("No images found in the project.")

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
        if not self.has_images():
            raise BakeryImageNotFoundError("No images found in the project.")

        bake_plan = self.render_bake_plan(image_name, image_version, image_type)
        build_file = self.context / ".docker-bake.json"
        with open(build_file, "w") as f:
            f.write(bake_plan.model_dump_json(indent=2) + "\n")

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
    ) -> List[Tuple[ImageVariant, Dict[str, str], List[str]]]:
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

            # Set the output options for Goss
            run_env["GOSS_OPTS"] = "--format json --no-color"

            # Append the target image tag, assuming the first one is valid to use and no duplications exist
            cmd.append(variant.tags[0])

            # Append the goss command to run or use the default `sleep infinity`
            cmd.extend(variant.goss.command.split() or ["sleep", "infinity"])

            dgoss_commands.append((variant, run_env, cmd))

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
        if not self.has_images():
            raise BakeryImageNotFoundError("No images found in the project.")

        dgoss_commands = self.render_dgoss_commands(image_name, image_version, image_type, runtime_options)

        results_dir = self.context / "dgoss_results"
        if results_dir.exists():
            shutil.rmtree(results_dir)
        results_dir.mkdir()

        errors = []
        for variant, env, cmd in dgoss_commands:
            log.info(f"[bright_blue bold]=== Running Goss tests for {variant.tags[0]} ===")
            filtered_env_vars = {k: v for k, v in env.items() if "GOSS" in k}
            log.debug(f"[bright_black]Environment variables: {filtered_env_vars}")
            log.debug(f"[bright_black]Executing dgoss command: {' '.join(cmd)}")
            p = subprocess.run(cmd, env=env, cwd=self.context, capture_output=True)

            uid = target_uid(variant.meta.name, variant.meta.version, variant)
            image_subdir = results_dir / variant.meta.name
            image_subdir.mkdir(exist_ok=True)
            results_file = image_subdir / f"{uid}.json"
            with open(results_file, "w") as f:
                try:
                    output = p.stdout.decode("utf-8")
                    output = output.strip()
                except UnicodeDecodeError:
                    log.warning(f"Unexpected encoding for dgoss output for image '{variant.tags[0]}'.")
                    output = p.stdout
                try:
                    output = json.dumps(json.loads(output), indent=2)
                except json.JSONDecodeError as e:
                    log.warning(f"Failed to decode JSON output from dgoss for image '{variant.tags[0]}': {e}")
                f.write(output)

            if p.returncode != 0:
                log.error(f"dgoss for image '{variant.tags[0]}' exited with code {p.returncode}")
                errors.append(
                    BakeryToolRuntimeError(
                        f"Subprocess call to dgoss exited with code {p.returncode}",
                        "dgoss",
                        cmd=cmd,
                        stdout=p.stdout,
                        stderr=p.stderr,
                        exit_code=p.returncode,
                        metadata={"results": results_file, "environment_variables": filtered_env_vars},
                    )
                )
            else:
                log.info(f"[bright_green bold]=== Goss tests passed for {variant.tags[0]} ===")

        if errors:
            if len(errors) == 1:
                raise errors[0]
            raise BakeryToolRuntimeErrorGroup(
                f"dgoss runtime errors occurred for multiple images.", errors
            )

    def _get_snyk_container_test_arguments(self, variant: ImageVariant) -> List[str]:
        result_dir = self.context / "snyk_test"
        uid = target_uid(variant.meta.name, variant.meta.version, variant)
        opts = []
        # Add output options
        if variant.meta.snyk.test.output.format == "json":
            opts.append("--json")
        elif variant.meta.snyk.test.output.format == "sarif":
            opts.append("--sarif")

        # Add output file options
        if variant.meta.snyk.test.output.json_file:
            result_dir.mkdir(exist_ok=True)
            opts.append(f"--json-file-output={str(result_dir / f"{uid}.json")}")
        elif variant.meta.snyk.test.output.sarif_file:
            result_dir.mkdir(exist_ok=True)
            opts.append(f"--sarif-file-output={str(result_dir / f"{uid}.sarif")}")

        # Add severity threshold
        opts.append(f"--severity-threshold={variant.meta.snyk.test.severity_threshold.value}")

        # Include options
        if variant.meta.snyk.test.include_app_vulns:
            opts.append("--app-vulns")
        else:
            opts.append("--exclude-app-vulns")

        if not variant.meta.snyk.test.include_base_image_vulns:
            opts.append("--exclude-base-image-vulns")

        if not variant.meta.snyk.test.include_node_modules:
            opts.append("--exclude-node-modules")

        return opts

    @staticmethod
    def _get_snyk_container_monitor_arguments(variant: ImageVariant) -> List[str]:
        opts = []
        # Add output options
        if variant.meta.snyk.monitor.output_json:
            opts.append("--json")

        # Add environment
        if variant.meta.snyk.monitor.environment is not None:
            project_environment = ",".join([e.value for e in variant.meta.snyk.monitor.environment])
            opts.append(f"--project-environment={project_environment}")

        # Add lifecycle
        if variant.meta.snyk.monitor.lifecycle is not None:
            project_lifecycle = ",".join([e.value for e in variant.meta.snyk.monitor.lifecycle])
            opts.append(f"--project-lifecycle={project_lifecycle}")

        # Add business criticality
        if variant.meta.snyk.monitor.business_criticality is not None:
            project_business_criticality = ",".join([e.value for e in variant.meta.snyk.monitor.business_criticality])
            opts.append(f"--project-business-criticality={project_business_criticality}")

        # Add tags
        if variant.meta.snyk.monitor.tags:
            str_tags = ",".join([f"{tag}={value}" for tag, value in variant.meta.snyk.monitor.tags.items()])
            opts.append(f"--project-tags='{str_tags}'")

        # Include options
        if not variant.meta.snyk.monitor.include_node_modules:
            opts.append("--exclude-node-modules")

        return opts

    @staticmethod
    def _get_snyk_container_sbom_arguments(variant: ImageVariant) -> List[str]:
        opts = [f"--format={variant.meta.snyk.sbom.format.value}"]

        if not variant.meta.snyk.sbom.include_app_vulns:
            opts.append("--exclude-app-vulns")

        return opts

    def render_snyk_commands(
            self,
            subcommand: str,
            image_name: str = None,
            image_version: str = None,
            image_type: str = None,
    ) -> List[Tuple[str, Dict[str, str], List[str]]]:
        snyk_bin = util.find_bin(self.context, "snyk", "SNYK_PATH") or "snyk"
        snyk_commands = []

        _filter: ImageFilter = ImageFilter(
            image_name=image_name,
            image_version=image_version,
            target_type=image_type,
        )
        images: Images = self.images.filter(_filter) if _filter else self.images

        for variant in images.variants:
            run_env = os.environ.copy()
            cmd = [snyk_bin, "container", subcommand]

            # Override the `--org` if `SNYK_ORG` is set
            if "SNYK_ORG" in os.environ:
                cmd.append(f"--org={os.environ['SNYK_ORG']}")

            if subcommand in [SnykContainerSubcommand.test.value, SnykContainerSubcommand.monitor.value]:
                # Set the project name to the image name
                cmd.append(f"--project-name={variant.meta.name}")
                # Set Containerfile path
                cmd.append(f"--file={str(variant.containerfile)}")
                # Set the path to the policy file if applicable
                if variant.snyk_policy_file is not None:
                    cmd.append(f"--policy-path={str(variant.snyk_policy_file)}")

            if subcommand == SnykContainerSubcommand.test.value:
                cmd.extend(self._get_snyk_container_test_arguments(variant))
            elif subcommand == SnykContainerSubcommand.monitor.value:
                cmd.extend(self._get_snyk_container_monitor_arguments(variant))
            elif subcommand == SnykContainerSubcommand.sbom.value:
                run_env["BAKERY_IMAGE_UID"] = target_uid(variant.meta.name, variant.meta.version, variant)
                run_env["BAKERY_SBOM_FORMAT"] = variant.meta.snyk.sbom.format.value.split("+")[1]
                cmd.extend(self._get_snyk_container_sbom_arguments(variant))

            cmd.append(variant.tags[0])

            snyk_commands.append((variant.tags[0], run_env, cmd))

        return snyk_commands

    def snyk(
            self,
            subcommand: str = None,
            image_name: str = None,
            image_version: str = None,
            image_type: str = None,
    ) -> None:
        snyk_bin = util.find_bin(self.context, "snyk", "SNYK_PATH") or "snyk"

        if subcommand not in SnykContainerSubcommand:
            raise BakeryToolError("snyk subcommand must be 'test', 'monitor', or 'sbom'.", "snyk")

        p = subprocess.run([snyk_bin, "config", "get", "org"], cwd=self.context, capture_output=True)
        if not p.stdout.decode("utf-8") and "SNYK_ORG" not in os.environ:
            log.warning(
                "Neither `snyk config get org` or `SNYK_ORG` environment variable are set. For best results, set your "
                "Snyk organization ID in the `snyk config` or in the `SNYK_ORG` environment variable."
            )

        snyk_commands = self.render_snyk_commands(subcommand, image_name, image_version, image_type)
        errors = []
        for tag, env, cmd in snyk_commands:
            log.info(f"[bright_blue bold]=== Running snyk container {subcommand.value} for {tag} ===")
            log.debug(f"[bright_black]Executing snyk command: {' '.join(cmd)}")

            kwargs = {"env": env, "cwd": self.context}
            if subcommand == SnykContainerSubcommand.sbom:
                kwargs["capture_output"] = True
            p = subprocess.run(cmd, **kwargs)

            if p.returncode != 0:
                exit_meaning = get_exit_code_meaning(subcommand, p.returncode)
                if exit_meaning["completed"]:
                    log.warning(
                        f"snyk container {subcommand.value} command for image '{tag}' completed with errors: "
                        f"{exit_meaning["reason"]}"
                    )
                else:
                    log.error(
                        f"snyk container {subcommand.value} command for image '{tag}' exited with code {p.returncode}: "
                        f"{exit_meaning["reason"]}"
                    )
                errors.append(
                    BakeryToolRuntimeError(
                        f"snyk container {subcommand.value} command for image '{tag}' exited with code {p.returncode}: "
                        f"{exit_meaning["reason"]}",
                        "snyk",
                        cmd=cmd,
                        stdout=p.stdout,
                        stderr=p.stderr,
                        exit_code=p.returncode,
                    )
                )
            else:
                log.info(
                    f"[bright_green bold]snyk container {subcommand.value} command "
                    f"for image '{tag}' completed successfully."
                )

            # FIXME: Clean this up as part of #91
            if subcommand == SnykContainerSubcommand.sbom:
                result_dir = self.context / "snyk_sbom"
                result_dir.mkdir(exist_ok=True)

                try:
                    output = p.stdout.decode("utf-8")
                except UnicodeDecodeError:
                    log.warning(f"Unexpected encoding for snyk container sbom output for image '{tag}'.")
                    output = p.stdout
                try:
                    output = json.loads(output)
                    output = json.dumps(output, indent=2)
                except json.JSONDecodeError:
                    log.warning(f"Failed to parse snyk container sbom output as JSON for image '{tag}'.")

                with open(result_dir / f"{env['BAKERY_IMAGE_UID']}.{env['BAKERY_SBOM_FORMAT']}", "w") as f:
                    log.info(
                        f"Writing SBOM to {result_dir / f'{env['BAKERY_IMAGE_UID']}.{env['BAKERY_SBOM_FORMAT']}'}."
                    )
                    f.write(output)

        if errors:
            if len(errors) == 1:
                raise errors[0]
            raise BakeryToolRuntimeErrorGroup(
                f"snyk container {subcommand.value} runtime errors occurred for multiple images.", errors
            )
