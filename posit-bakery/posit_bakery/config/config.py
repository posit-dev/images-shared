import logging
import os
import re
import shutil
from pathlib import Path

import jinja2
from pydantic import Field, model_validator, computed_field, field_validator
from typing import Annotated, Self
from ruamel.yaml import YAML

from posit_bakery import util
from posit_bakery.config.registry import Registry
from posit_bakery.config.repository import Repository
from posit_bakery.config.shared import BakeryPathMixin, BakeryYAMLModel
from posit_bakery.config.image import Image
from posit_bakery.config.templating import TPL_CONTAINERFILE, TPL_BAKERY_CONFIG_YAML
from posit_bakery.config.templating.filters import jinja2_env
from posit_bakery.const import DEFAULT_BASE_IMAGE
from posit_bakery.error import BakeryToolRuntimeError, BakeryToolRuntimeErrorGroup
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
        return list(unique_registries)

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
            image_path.mkdir()

        image_template_path = image_path / "template"
        if not image_template_path.is_dir():
            log.debug(f"Creating new image templates directory [bold]{image_template_path}")
            image_template_path.mkdir()

        # Best guess a good name for the Containerfile template.
        containerfile_base_name = "Containerfile"
        containerfile_name = containerfile_base_name
        if base_tag:
            base_tag_extension = re.sub(r"[^a-zA-Z0-9_-]", "", base_tag.lower())
            containerfile_name += f".{base_tag_extension}"
        containerfile_name += ".jinja2"

        # Create a new Containerfile template if it doesn't exist
        containerfile_glob = image_template_path.glob(f"{containerfile_base_name}*.jinja2")
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

    def create_image_model(self, name: str, subpath: str | None = None) -> Image:
        """Creates a new image directory and adds it to the config.

        This function does **NOT** create the image files template. Use `create_image_files_template` for that.

        :param name: The name of the image to create.
        :param subpath: Optional alternate subpath for the image.
        :return: The newly created Image model.
        """
        args = {"name": name, "parent": self}
        if subpath:
            args["subpath"] = subpath
        new_image = Image(**args)
        self.images.append(new_image)
        return new_image


class BakeryConfig:
    """Manager for the bakery.yaml configuration file and operations against the configuration.

    :var yaml: The YAML parser used to read and write the bakery.yaml file.
    :var config_file: Path to the bakery.yaml configuration file.
    :var base_path: The base path where the bakery.yaml file is located.
    :var model: The BakeryConfigDocument model representation of the bakery.yaml file.
    :var targets: List of ImageTarget objects representing the image build targets defined in the config.
    """

    def __init__(self, config_file: str | Path | os.PathLike):
        """Initializes the BakeryConfig with the given config file path.

        :param config_file: Path to the target bakery.yaml configuration file.
        """
        self.yaml = YAML()
        self.config_file = Path(config_file)
        if not self.config_file.exists():
            raise FileNotFoundError(f"File '{self.config_file}' does not exist.")
        self.base_path = self.config_file.parent
        self._config_yaml = self.yaml.load(self.config_file) or dict()
        self.model = BakeryConfigDocument(base_path=self.base_path, **self._config_yaml)
        self.targets = []
        self.generate_image_targets()

    @staticmethod
    def new(base_path: str | Path | os.PathLike) -> None:
        """Creates a new bakery.yaml file in the given base path.

        :var base_path: The path where the new bakery.yaml file will be created.
        """
        config_file = Path(base_path) / "bakery.yaml"
        log.info(f"Creating new project config file [bold]{config_file}")
        tpl = jinja2_env(loader=jinja2.FileSystemLoader(config_file.parent)).from_string(TPL_BAKERY_CONFIG_YAML)
        rendered = tpl.render(repo_url=util.try_get_repo_url(base_path))
        with open(config_file, "w") as f:
            f.write(rendered)

    def write(self) -> None:
        """Write the bakery config to the config file."""
        self.yaml.dump(self._config_yaml, self.config_file)

    def create_image(self, image_name: str, subpath: str | None = None, base_image: str | None = None):
        """Creates a new image.

        Creates a new image directory, adds the image to the config, and writes the image back to bakery.yaml.

        :param image_name: The name of the image to create.
        :param subpath: Optional subpath for the image. If not provided, the image name will be used as the subpath.
        :param base_image: Optional base image to use in the Containerfile template. This is used in the `FROM`
            directive.
        """
        if self.model.get_image(image_name):
            raise ValueError(f"Image '{image_name}' already exists in config.")
        new_image = self.model.create_image_model(image_name, subpath)
        self.model.create_image_files_template(new_image.path, new_image.name, base_image or DEFAULT_BASE_IMAGE)
        self._config_yaml.setdefault("images", []).append(
            new_image.model_dump(exclude_defaults=True, exclude_none=True, exclude_unset=True)
        )
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
            version_name=version, subpath=subpath, latest=latest, update_if_exists=force
        )
        image.create_version_files(new_version, image.variants, values)

        self.write()

    def generate_image_targets(self):
        """Generates image targets from the images defined in the config."""
        # TODO: Support filtering of images here
        targets = []
        for image in self.model.images:
            for variant in image.variants:
                for version in image.versions:
                    for _os in version.os:
                        targets.append(
                            ImageTarget.new_image_target(
                                repository=self.model.repository,
                                image_version=version,
                                image_variant=variant,
                                image_os=_os,
                            )
                        )

        self.targets = targets

    def build_targets(
        self,
        load: bool = True,
        push: bool = False,
        cache: bool = True,
        strategy: ImageBuildStrategy = ImageBuildStrategy.BAKE,
    ):
        """Build image targets using the specified strategy.

        :param load: If True, load the built images into the local Docker daemon.
        :param push: If True, push the built images to the configured registries.
        :param cache: If True, use the build cache when building images.
        :param strategy: The strategy to use when building images.
        """
        # TODO: Implement an "remove after push" option to remove local images after pushing.
        if strategy == ImageBuildStrategy.BAKE:
            bake_plan = BakePlan.from_image_targets(context=self.base_path, image_targets=self.targets)
            bake_plan.build(load=load, push=push, cache=cache)
        elif strategy == ImageBuildStrategy.BUILD:
            for target in self.targets:
                # TODO: Implement error aggregation and add a fail-fast option.
                target.build(load=load, push=push, cache=cache)

    def dgoss_targets(
        self,
    ) -> tuple[GossJsonReportCollection, BakeryToolRuntimeError | BakeryToolRuntimeErrorGroup | None]:
        """Run dgoss tests for all image targets.

        :return: A tuple containing the GossJsonReportCollection and any errors encountered during the tests.
        """
        suite = DGossSuite(self.base_path, self.targets)
        return suite.run()
