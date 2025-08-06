import logging
import os
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

    @staticmethod
    def create_image_templates(image_path: Path, image_name: str, base_tag: str):
        exists: bool = image_path.is_dir()
        if not exists:
            log.debug(f"Creating new image directory [bold]{image_path}")
            image_path.mkdir()

        image_template_path = image_path / "template"
        if not image_template_path.is_dir():
            log.debug(f"Creating new image templates directory [bold]{image_template_path}")
            image_template_path.mkdir()

        # Create a new Containerfile template if it doesn't exist
        containerfile_path = image_template_path / "Containerfile.jinja2"
        if not containerfile_path.is_file():
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

    def create_image(self, name: str, subpath: str | None = None) -> Image:
        """Creates a new image directory and adds it to the config."""
        args = {"name": name, "parent": self}
        if subpath:
            args["subpath"] = subpath
        new_image = Image(**args)
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
        self.targets = []
        self.generate_image_targets()

    @staticmethod
    def new(base_path: str | Path | os.PathLike) -> None:
        """Creates a new bakery.yaml file in the given base path."""
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
        """Creates a new image directory, adds it to the config, and writes the config to bakery.yaml."""
        if self.model.get_image(image_name):
            raise ValueError(f"Image '{image_name}' already exists in config.")
        new_image = self.model.create_image(image_name, subpath)
        self.model.create_image_templates(new_image.path, new_image.name, base_image or DEFAULT_BASE_IMAGE)
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

        # Create the version in the image model.
        new_version = image.create_version(version_name=version, subpath=subpath, latest=latest, update_if_exists=force)
        image.render_version_from_template(new_version, image.variants, values)

        self.write()

    def generate_image_targets(self):
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
        """Build image targets using the specified strategy."""
        if strategy == ImageBuildStrategy.BAKE:
            bake_plan = BakePlan.from_image_targets(context=self.base_path, image_targets=self.targets)
            bake_plan.build(load=load, push=push, cache=cache)
        elif strategy == ImageBuildStrategy.BUILD:
            for target in self.targets:
                target.build(load=load, push=push, cache=cache)

    def dgoss_targets(
        self,
    ) -> tuple[GossJsonReportCollection, BakeryToolRuntimeError | BakeryToolRuntimeErrorGroup | None]:
        """Run dgoss tests for all image targets."""
        suite = DGossSuite(self.base_path, self.targets)
        return suite.run()
