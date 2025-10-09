import atexit
import logging
import os
import re
import shutil
from pathlib import Path

import jinja2
import pydantic
from pydantic import Field, model_validator, field_validator, BaseModel
from typing import Annotated, Self

from python_on_whales import DockerException
from ruamel.yaml import YAML

from posit_bakery import util
from posit_bakery.config.registry import Registry
from posit_bakery.config.repository import Repository
from posit_bakery.config.shared import BakeryPathMixin, BakeryYAMLModel
from posit_bakery.config.image import Image
from posit_bakery.config.templating import TPL_CONTAINERFILE, TPL_BAKERY_CONFIG_YAML
from posit_bakery.config.templating.render import jinja2_env
from posit_bakery.const import DEFAULT_BASE_IMAGE, DevVersionInclusionEnum
from posit_bakery.error import (
    BakeryToolRuntimeError,
    BakeryToolRuntimeErrorGroup,
    BakeryFileError,
    BakeryBuildErrorGroup,
    BakeryTemplateErrorGroup,
)
from posit_bakery.image.goss.dgoss import DGossSuite
from posit_bakery.image.goss.report import GossJsonReportCollection
from posit_bakery.image.image_target import ImageTarget, ImageBuildStrategy
from posit_bakery.image.bake.bake import BakePlan

log = logging.getLogger(__name__)


class BakeryConfigDocument(BakeryPathMixin, BakeryYAMLModel):
    """Model representation of the top-level bakery.yaml configuration document."""

    base_path: Annotated[
        Path, Field(exclude=True, description="Path to the parent directory of the bakery.yaml config file.")
    ]
    repository: Annotated[Repository, Field(description="Repository configuration for the Bakery project.")]
    registries: Annotated[
        list[Registry],
        Field(
            default_factory=list,
            validate_default=True,
            description="List of global registries for images in the Bakery project.",
        ),
    ]
    images: Annotated[
        list[Image],
        Field(default_factory=list, validate_default=True, description="List of images in the Bakery project."),
    ]

    @field_validator("registries", mode="after")
    @classmethod
    def deduplicate_registries(cls, registries: list[Registry]) -> list[Registry]:
        """Ensures that the registries list is unique. Warns if duplicates are found.

        :param registries: List of Registry objects to deduplicate.
        """
        unique_registries = set(registries)
        for unique_registry in unique_registries:
            if registries.count(unique_registry) > 1:
                log.warning(f"Duplicate registry defined in config: {unique_registry.base_url}")
        return sorted(list(unique_registries), key=lambda r: r.base_url)

    @field_validator("images", mode="after")
    @classmethod
    def check_images_not_empty(cls, images: list[Image]) -> list[Image]:
        """Ensures that the images list is not empty. Warns if no images are found.

        :param images: List of Image objects to check.
        """
        if len(images) == 0:
            log.warning("No images found in the Bakery config. At least one image is required for most commands.")
        return images

    @field_validator("images", mode="after")
    @classmethod
    def check_image_duplicates(cls, images: list[Image]) -> list[Image]:
        """Ensures that there are no duplicate image names in the config. Raises an error if duplicates are found.

        :param images: List of Image objects to check for duplicates.
        """
        error_message = ""
        seen_names = set()
        for image in images:
            if image.name in seen_names:
                if not error_message:
                    error_message = "Duplicate image names found in the bakery config:\n"
                error_message += f" - {image.name}\n"
            seen_names.add(image.name)
        if error_message:
            raise ValueError(error_message.strip())

        return images

    @model_validator(mode="after")
    def resolve_parentage(self) -> Self:
        """Sets the parent reference for the Repository and Image child objects."""
        self.repository.parent = self
        for image in self.images:
            image.parent = self
        return self

    @property
    def path(self) -> Path | None:
        """Returns the path to the bakery config parent directory."""
        return self.base_path

    def get_image(self, name: str) -> Image | None:
        """Returns an image by name, or None if not found.

        :param name: The name of the image to get.
        """
        for image in self.images:
            if image.name == name:
                return image
        return None

    @staticmethod
    def create_image_files_template(image_path: Path, image_name: str, base_tag: str):
        """Creates the necessary directories and files for a new image template.

        This function does **NOT** create a new image model. Use `create_image_model` for that.

        Creates the following structure:
        - image_path/
            - template/
                - Containerfile.{{ base_tag | condensed }}.jinja2
                - test/
                    - goss.yaml.jinja2
                - deps/
                    - packages.txt.jinja2

        :param image_path: The path to the image directory.
        :param image_name: The name of the image.
        :param base_tag: The base tag for the image to use in the `FROM` directive of the Containerfile template.
        """
        exists: bool = image_path.is_dir()
        if not exists:
            log.debug(f"Creating new image directory [bold]{image_path}")
            image_path.mkdir(parents=True)

        image_template_path = image_path / "template"
        if not image_template_path.is_dir():
            log.debug(f"Creating new image templates directory [bold]{image_template_path}")
            image_template_path.mkdir()

        # Create a new Containerfile template if it doesn't exist
        containerfile_name = "Containerfile.jinja2"
        containerfile_glob = image_template_path.glob(f"Containerfile*.jinja2")
        if not any(containerfile_path.is_file() for containerfile_path in containerfile_glob):
            containerfile_path = image_template_path / containerfile_name
            log.debug(f"Creating new Containerfile template [bold]{containerfile_path}")
            tpl = jinja2_env().from_string(TPL_CONTAINERFILE)
            rendered = tpl.render(image_name=image_name, base_tag=base_tag)
            with open(containerfile_path, "w") as f:
                f.write(rendered)

        image_test_path = image_template_path / "test"
        if not image_test_path.is_dir():
            log.debug(f"Creating new image templates test directory [bold]{image_test_path}")
            image_test_path.mkdir()
        image_test_goss_file = image_test_path / "goss.yaml.jinja2"
        image_test_goss_file.touch(exist_ok=True)

        image_deps_path = image_template_path / "deps"
        if not image_deps_path.is_dir():
            log.debug(f"Creating new image templates dependencies directory [bold]{image_deps_path}")
            image_deps_path.mkdir()
        image_deps_package_file = image_deps_path / "packages.txt.jinja2"
        image_deps_package_file.touch(exist_ok=True)

    def create_image_model(
        self,
        name: str,
        subpath: str | None = None,
        display_name: str | None = None,
        description: str | None = None,
        documentation_url: str | None = None,
    ) -> Image:
        """Creates a new image directory and adds it to the config.

        This function does **NOT** create the image files template. Use `create_image_files_template` for that.

        :param name: The name of the image to create.
        :param subpath: Optional alternate subpath for the image.
        :param display_name: Optional display name for the image. If not provided, the image name will be used.
        :param description: Optional description for the image. Used in labels.
        :param documentation_url: Optional URL for the image documentation. Used in labels.

        :return: The newly created Image model.
        """
        args = {"name": name, "parent": self}
        if subpath:
            args["subpath"] = subpath
        if display_name:
            args["displayName"] = display_name
        if description:
            args["description"] = description
        if documentation_url:
            args["documentationUrl"] = documentation_url

        new_image = Image(**args)
        self.images.append(new_image)

        return new_image


class BakeryConfigFilter(BaseModel):
    """Container for filtering options when generating image targets from the BakeryConfig."""

    image_name: Annotated[
        str | None, Field(description="Name or regex pattern of the image to filter by.", default=None)
    ]
    image_variant: Annotated[
        str | None, Field(description="Name or regex pattern of the image variant to filter by.", default=None)
    ]
    image_version: Annotated[
        str | None, Field(description="Name or regex pattern of the image version to filter by.", default=None)
    ]
    image_os: Annotated[
        str | None, Field(description="Name or regex pattern of the image OS to filter by.", default=None)
    ]


class BakerySettings(BaseModel):
    """Container for global settings that can be applied to the BakeryConfig."""

    filter: BakeryConfigFilter = Field(
        default_factory=BakeryConfigFilter, description="Filter(s) to apply when generating image targets."
    )
    dev_versions: Annotated[
        DevVersionInclusionEnum,
        Field(
            description="Include or exclude development versions defined in config.",
            default=DevVersionInclusionEnum.EXCLUDE,
        ),
    ]
    clean_temporary: Annotated[
        bool, Field(description="Clean intermediary and temporary files created by Bakery.", default=True)
    ]
    cache_registry: Annotated[str | None, Field(description="Registry to use for image build cache.", default=None)]


class BakeryConfig:
    """Manager for the bakery.yaml configuration file and operations against the configuration.

    :var yaml: The YAML parser used to read and write the bakery.yaml file.
    :var config_file: Path to the bakery.yaml configuration file.
    :var base_path: The base path where the bakery.yaml file is located.
    :var model: The BakeryConfigDocument model representation of the bakery.yaml file.
    :var targets: List of ImageTarget objects representing the image build targets defined in the config.
    """

    def __init__(self, config_file: str | Path | os.PathLike, settings: BakerySettings | None = None):
        """Initializes the BakeryConfig with the given config file path.

        :param config_file: Path to the target bakery.yaml configuration file.
        :param settings: Optional BakeryConfigFilter to apply when generating image targets.

        :raises FileNotFoundError: If the config file does not exist.
        """
        if settings is None:
            settings = BakerySettings()
        self.settings = settings

        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.indent(mapping=2, sequence=4, offset=2)
        self.config_file = Path(config_file).resolve()
        if not self.config_file.exists():
            raise FileNotFoundError(f"File '{self.config_file}' does not exist.")
        self.base_path = self.config_file.parent
        self._config_yaml = self.yaml.load(self.config_file) or dict()
        try:
            self.model = BakeryConfigDocument(base_path=self.base_path, **self._config_yaml)
        except pydantic.ValidationError as e:
            log.error(f"Failed to load configuration from {str(self.config_file)}")
            raise e

        if self.settings.dev_versions in [DevVersionInclusionEnum.ONLY, DevVersionInclusionEnum.INCLUDE]:
            for image in self.model.images:
                image.load_dev_versions()
                image.create_ephemeral_version_files()
                if self.settings.clean_temporary:
                    atexit.register(image.remove_ephemeral_version_files)

        self.targets = []
        self.generate_image_targets(self.settings)

    @classmethod
    def from_context(cls, context: str | Path | os.PathLike, settings: BakerySettings | None = None) -> "BakeryConfig":
        """Creates a BakeryConfig instance from a given context path.

        :param context: The path to the bakery.yaml file or its parent directory.
        :param settings: Optional BakerySettings to apply when generating image targets.

        :return: A BakeryConfig instance.

        :raises FileNotFoundError: If no bakery.yaml or bakery.yml file is found in the context path.
        """
        if settings is None:
            settings = BakerySettings()

        context = Path(context).resolve()
        search_paths = [context / "bakery.yaml", context / "bakery.yml"]
        for file in search_paths:
            if file.is_file():
                log.info(f"Loading Bakery config from [bold]{file}")
                return cls(file, settings)

        raise BakeryFileError(
            f"No bakery.yaml file found in the context path '{context}'. Try running `bakery create project` first "
            f"if this is a new project."
        )

    @staticmethod
    def new(base_path: str | Path | os.PathLike) -> None:
        """Creates a new bakery.yaml file in the given base path.

        :var base_path: The path where the new bakery.yaml file will be created.
        """
        config_file = Path(base_path).resolve() / "bakery.yaml"
        log.info(f"Creating new project config file [bold]{config_file}")
        tpl = jinja2_env(loader=jinja2.FileSystemLoader(config_file.parent)).from_string(TPL_BAKERY_CONFIG_YAML)
        rendered = tpl.render(repo_url=util.try_get_repo_url(base_path))
        with open(config_file, "w") as f:
            f.write(rendered)

    def write(self) -> None:
        """Write the bakery config to the config file."""
        self.yaml.dump(self._config_yaml, self.config_file)

    def _get_image_index(self, image_name: str) -> int:
        """Returns the index of the image with the given name in the config.

        :param image_name: The name of the image to find.
        :return: The index of the image in the config, or -1 if not found.
        """

        for index, image in enumerate(self._config_yaml.get("images", [])):
            if image.get("name") == image_name:
                return index
        return -1

    def _get_version_index(self, image_name: str, version_name: str) -> int:
        """Returns the index of the version with the given name in the image's versions list.

        :param image_name: The name of the image in the config to which the version belongs.
        :param version_name: The name of the version to find.
        :return: The index of the version in the image's versions list, or -1 if not found.
        """
        image_index = self._get_image_index(image_name)
        for index, version in enumerate(self._config_yaml["images"][image_index].get("versions", [])):
            if version["name"] == version_name:
                return index
        return -1

    def create_image(
        self,
        image_name: str,
        base_image: str | None = None,
        subpath: str | None = None,
        display_name: str | None = None,
        description: str | None = None,
        documentation_url: str | None = None,
    ):
        """Creates a new image.

        Creates a new image directory, adds the image to the config, and writes the image back to bakery.yaml.

        :param image_name: The name of the image to create.
        :param base_image: Optional base image to use in the Containerfile template. This is used in the `FROM`
            directive.
        :param subpath: Optional subpath for the image. If not provided, the image name will be used as the subpath.
        :param display_name: Optional display name for the image. If not provided, the image name will be used.
        :param description: Optional description for the image. Used in labels.
        :param documentation_url: Optional URL for the image documentation. Used in labels.
        """
        if self.model.get_image(image_name):
            raise ValueError(f"Image '{image_name}' already exists in config.")
        new_image = self.model.create_image_model(
            image_name,
            subpath=subpath,
            display_name=display_name,
            description=description,
            documentation_url=documentation_url,
        )
        self.model.create_image_files_template(new_image.path, new_image.name, base_image or DEFAULT_BASE_IMAGE)
        new_image_dict = new_image.model_dump(exclude_defaults=True, exclude_none=True, exclude_unset=True)
        self._config_yaml.setdefault("images", []).append(new_image_dict)
        self.write()

    def create_version(
        self,
        image_name: str,
        version: str,
        subpath: str | None = None,
        values: dict[str, str] | None = None,
        latest: bool = True,
        force: bool = False,
    ) -> None:
        """Creates a new version for an image.

        Creates a new version directory from image templates, add the version to the image config, and writes the
        version back to bakery.yaml.

        :param image_name: The name of the image to create the version for.
        :param version: The version name to create.
        :param subpath: Optional subpath for the version. If not provided, the version name will be used as the subpath.
        :param values: Optional dictionary of values to use in the version. This can be used to provide additional
            context or configuration for the version. Often used to specify versions of R, Python, or Quarto.
        :param latest: Whether this version should be marked as the latest version.
        :param force: If True, will overwrite an existing version with the same name.
        """
        # TODO: In the future, we should have some sort of "values" completion function called here. This would add or
        #       complete common values such as R, Python, and Quarto versions.
        image = self.model.get_image(image_name)
        if image is None:
            raise ValueError(f"Image '{image_name}' does not exist in the config.")
        existing_version = image.get_version(version)
        if existing_version is not None and not force:
            raise ValueError(f"Version '{version}' already exists for image '{image_name}'. Use --force to overwrite.")

        version_path = self.base_path / image_name / (subpath or version)

        # If the version already exists, some checks will be performed.
        if existing_version is not None:
            # If the version already exists, we check if the subpaths match.
            if existing_version.subpath != (subpath or version):
                # If the subpaths do not match, we move the existing subpath to the new subpath.
                existing_version_path = self.base_path / image_name / existing_version.subpath
                shutil.move(existing_version_path, version_path)

        # Create the version in the image model.
        new_version = image.create_version_model(
            version_name=version, subpath=subpath, values=values, latest=latest, update_if_exists=force
        )

        # Add version to the YAML config.
        image_index = self._get_image_index(image_name)
        if latest and self._config_yaml["images"][image_index].get("versions", []):
            # If this is the latest version, we need to remove the latest flag from any other versions.
            for v in self._config_yaml["images"][image_index]["versions"]:
                if v.get("latest", False) and v["name"] != version:
                    v.pop("latest", None)
        if not existing_version:
            self._config_yaml["images"][image_index].setdefault("versions", []).append(
                new_version.model_dump(exclude_defaults=True, exclude_none=True, exclude_unset=True)
            )
        else:
            version_index = self._get_version_index(image_name, version)
            self._config_yaml["images"][image_index]["versions"][version_index] = new_version.model_dump(
                exclude_defaults=True, exclude_none=True, exclude_unset=True
            )
        # Sort versions.
        self._config_yaml["images"][image_index]["versions"].sort(key=lambda v: v["name"], reverse=True)

        # Create the version directory and files.
        image.create_version_files(new_version, image.variants)

        self.write()

    def patch_version(
        self,
        image_name: str,
        old_version: str,
        new_version: str,
        values: dict[str, str] | None = None,
        clean: bool = True,
    ) -> "ImageVersion":
        """Patches an existing image version with a new version and regenerates templates."""
        image = self.model.get_image(image_name)

        if image is None:
            raise ValueError(f"Image '{image_name}' does not exist in the config.")

        image_index = self._get_image_index(image_name)
        # These checks should never fail, but we include them for safety since otherwise the last element will rewrite.
        if image_index == -1:
            raise ValueError(f"Image '{image_name}' does not exist in bakery.yaml.")

        version_index = self._get_version_index(image_name, old_version)
        # These checks should never fail, but we include them for safety since otherwise the last element will rewrite.
        if version_index == -1:
            raise ValueError(f"Version '{old_version}' does not exist for image '{image_name}' in bakery.yaml.")

        patched_version = image.patch_version(old_version, new_version, values=values, clean=clean)

        self._config_yaml["images"][image_index]["versions"][version_index] = patched_version.model_dump(
            exclude_defaults=True, exclude_none=True, exclude_unset=True
        )

        self.write()

        return patched_version

    def regenerate_version_files(
        self, _filter: BakeryConfigFilter | None = None, regex_filters: list[str] | None = None
    ):
        """Regenerates version files from templates matching the given filters.

        :param _filter: A BakeryConfigFilter to apply when regenerating version files.
        :param regex_filters: A list of regex patterns to filter which templates to render.

        :raises BakeryFileError: If any errors occur while regenerating version files.
        """
        _filter = _filter or BakeryConfigFilter()
        regex_filters = regex_filters or []
        exception_list = []

        for image in self.model.images:
            if _filter.image_name is not None and re.search(_filter.image_name, image.name) is None:
                log.debug(f"Skipping image '{image.name}' due to not matching name filter '{_filter.image_name}'")
                continue
            for version in image.versions:
                if _filter.image_version is not None and re.search(_filter.image_version, version.name) is None:
                    log.debug(
                        f"Skipping image version '{version.name}' in image '{image.name}' "
                        f"due to not matching version filter '{_filter.image_version}'"
                    )
                    continue

                log.info(f"Rendering templates for image '{image.name}' version '{version.name}'")
                try:
                    image.create_version_files(version, image.variants, regex_filters=regex_filters)
                except Exception as e:
                    log.error(f"Failed to regenerate files for image '{image.name}' version '{version.name}'.")
                    exception_list.append(e)

        if exception_list:
            if len(exception_list) == 1:
                raise exception_list[0]
            raise BakeryTemplateErrorGroup(
                "Multiple errors occurred while updating files from templates.", exception_list
            )

    def generate_image_targets(self, settings: BakerySettings = BakerySettings()):
        """Generates image targets from the images defined in the config.

        :param settings: Optional settings to apply when generating image targets. If None, all images will be included.
        """
        targets: list[ImageTarget] = []
        for image in self.model.images:
            if settings.filter.image_name is not None and re.search(settings.filter.image_name, image.name) is None:
                log.debug(
                    f"Skipping image '{image.name}' due to not matching name filter '{settings.filter.image_name}'"
                )
                continue
            for version in image.versions:
                if settings.dev_versions == DevVersionInclusionEnum.ONLY and not version.isDevelopmentVersion:
                    log.debug(
                        f"Skipping image version '{version.name}' in image '{image.name}' due to not being a "
                        f"development version."
                    )
                    continue
                if (
                    settings.filter.image_version is not None
                    and re.search(settings.filter.image_version, version.name) is None
                ):
                    log.debug(
                        f"Skipping image version '{version.name}' in image '{image.name}' "
                        f"due to not matching version filter '{settings.filter.image_version}'"
                    )
                    continue
                for variant in image.variants or [None]:
                    if (
                        settings.filter.image_variant is not None
                        and re.search(settings.filter.image_variant, variant.name) is None
                    ):
                        log.debug(
                            f"Skipping image variant '{variant.name}' in image '{image.name}' "
                            f"due to not matching variant filter '{settings.filter.image_variant}'"
                        )
                        continue
                    for _os in version.os or [None]:
                        if (
                            settings.filter.image_os is not None
                            and re.search(settings.filter.image_os, _os.name) is None
                        ):
                            log.debug(
                                f"Skipping image OS '{_os.name}' in image '{image.name}' "
                                f"due to not matching OS filter '{settings.filter.image_os}'"
                            )
                            continue
                        targets.append(
                            ImageTarget.new_image_target(
                                repository=self.model.repository,
                                image_version=version,
                                image_variant=variant,
                                image_os=_os,
                            )
                        )

        targets = sorted(targets, key=lambda t: str(t))
        self.targets = targets

    def bake_plan_targets(self) -> str:
        """Generates a bake plan JSON string for the image targets defined in the config."""
        bake_plan = BakePlan.from_image_targets(
            context=self.base_path, image_targets=self.targets, cache_registry=self.settings.cache_registry
        )
        return bake_plan.model_dump_json(indent=2, exclude_none=True, by_alias=True)

    def build_targets(
        self,
        load: bool = True,
        push: bool = False,
        cache: bool = True,
        strategy: ImageBuildStrategy = ImageBuildStrategy.BAKE,
        fail_fast: bool = False,
    ):
        """Build image targets using the specified strategy.

        :param load: If True, load the built images into the local Docker daemon.
        :param push: If True, push the built images to the configured registries.
        :param cache: If True, use the build cache when building images.
        :param cache_from: Optional list of cache sources to use when building images.
        :param cache_to: Optional list of cache destinations to use when building images.
        :param strategy: The strategy to use when building images.
        :param fail_fast: If True, stop building targets on the first failure.
        """
        if strategy == ImageBuildStrategy.BAKE:
            bake_plan = BakePlan.from_image_targets(
                context=self.base_path, image_targets=self.targets, cache_registry=self.settings.cache_registry
            )
            bake_plan.build(
                load=load,
                push=push,
                cache=cache,
                clean_bakefile=self.settings.clean_temporary,
            )
        elif strategy == ImageBuildStrategy.BUILD:
            errors: list[Exception] = []
            for target in self.targets:
                try:
                    target.build(load=load, push=push, cache=cache, cache_registry=self.settings.cache_registry)
                except (BakeryFileError, DockerException) as e:
                    log.error(f"Failed to build image target '{str(target)}'.")
                    if fail_fast:
                        log.info("--fail-fast is set, stopping builds...")
                        raise e
                    errors.append(e)
            if errors:
                if len(errors) == 1:
                    raise errors[0]
                raise BakeryBuildErrorGroup("Multiple errors occurred while building images.", errors)

    def dgoss_targets(
        self,
    ) -> tuple[GossJsonReportCollection, BakeryToolRuntimeError | BakeryToolRuntimeErrorGroup | None]:
        """Run dgoss tests for all image targets.

        :return: A tuple containing the GossJsonReportCollection and any errors encountered during the tests.
        """
        suite = DGossSuite(self.base_path, self.targets)
        return suite.run()
