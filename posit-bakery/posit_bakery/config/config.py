import logging
import os
import shutil
from pathlib import Path

from pydantic import Field, model_validator, computed_field, field_validator
from typing import Annotated, Self
from ruamel.yaml import YAML

from posit_bakery.config.registry import Registry
from posit_bakery.config.repository import Repository
from posit_bakery.config.shared import BakeryPathMixin, BakeryYAMLModel
from posit_bakery.config.image import Image
from posit_bakery.const import DEFAULT_BASE_IMAGE
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.templating.default import create_image_templates, render_image_templates


log = logging.getLogger(__name__)


class BakeryConfigDocument(BakeryPathMixin, BakeryYAMLModel):
    base_path: Annotated[Path, Field(exclude=True)]
    repository: Repository
    registries: Annotated[list[Registry], Field(default_factory=list, validate_default=True)]
    images: Annotated[list[Image], Field(default_factory=list, validate_default=True)]

    @field_validator("registries", mode="after")
    @classmethod
    def deduplicate_registries(cls, registries: list[Registry]) -> list[Registry]:
        """Ensures that the registries list is unique and sorted."""
        unique_registries = set(registries)
        for unique_registry in unique_registries:
            if registries.count(unique_registry) > 1:
                log.warning(f"Duplicate registry defined in config: {unique_registry.base_url}")
        return list(unique_registries)

    @field_validator("images", mode="after")
    @classmethod
    def check_images_not_empty(cls, images: list[Image]) -> list[Image]:
        """Ensures that the images list is not empty."""
        if len(images) == 0:
            log.warning("No images found in the Bakery config. At least one image is required for most commands.")
        return images

    @field_validator("images", mode="after")
    @classmethod
    def check_image_duplicates(cls, images: list[Image]) -> list[Image]:
        """Ensures that there are no duplicate image names in the config."""
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
        self.repository.parent = self
        for image in self.images:
            image.parent = self
        return self

    @computed_field
    @property
    def path(self) -> Path:
        """Returns the path to the bakery config directory."""
        return self.base_path

    def get_image(self, name: str) -> Image | None:
        """Returns an image by name, or None if not found."""
        for image in self.images:
            if image.name == name:
                return image
        return None

    def create_image(self, name: str) -> Image:
        """Creates a new image directory and adds it to the config."""
        new_image = Image(name=name, parent=self)
        self.images.append(new_image)
        return new_image


class BakeryConfig:
    def __init__(self, config_file: str | Path | os.PathLike):
        self.yaml = YAML()
        self.config_file = Path(config_file)
        if not self.config_file.exists():
            raise FileNotFoundError(f"File '{self.config_file}' does not exist.")
        self.base_path = self.config_file.parent
        self._config_yaml = self.yaml.load(self.config_file) or dict()
        self.model = BakeryConfigDocument(base_path=self.base_path, **self._config_yaml)
        self.targets = self.generate_image_targets()

    def write(self) -> None:
        """Write the bakery config to the config file."""
        self.yaml.dump(self._config_yaml, self.config_file)

    def create_image(self, image_name: str, base_image: str | None = None) -> None:
        """Creates a new image directory, adds it to the config, and writes the config to bakery.yaml."""
        if self.model.get_image(image_name):
            raise ValueError(f"Image '{image_name}' already exists in config.")
        create_image_templates(self.base_path / image_name, image_name, base_image or DEFAULT_BASE_IMAGE)
        new_image = self.model.create_image(image_name)
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
        """Creates a new version for an image and writes the config to bakery.yaml.

        version: str - The version to create. Should match the product's full version.
        subpath: str - The subpath to use as the subversion. This can be a condensed name.
        latest: bool - Whether to mark this version as the latest. Defaults to True. Other versions will be marked as
            not latest.
        force: bool - Whether to force rewriting of the version even if it already exists. Defaults to False.
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

        # Render the image templates.
        variants = [v.extension for v in image.variants]
        render_image_templates(
            context=version_path,
            version=version,
            template_values=values,
            targets=variants,
        )

        # Create the version in the image model.
        image.create_version(version=version, subpath=subpath, latest=latest, update_if_exists=force)

        self.write()

    def generate_image_targets(self) -> list[ImageTarget]:
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

        return targets
