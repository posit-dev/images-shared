import re
from copy import deepcopy
from pathlib import Path
from typing import Annotated, Self, Union

from pydantic import BaseModel, Field, model_validator, computed_field, field_validator

from posit_bakery.config.registry import Registry
from posit_bakery.config.shared import BakeryPathMixin, BakeryYAMLModel
from posit_bakery.config.tag import TagPattern, default_tag_patterns
from posit_bakery.config.tools import ToolField, default_tool_options


class ImageVersionOS(BakeryYAMLModel):
    parent: Annotated[Union[BaseModel, None] | None, Field(exclude=True, default=None)]
    name: str
    primary: Annotated[bool, Field(default=False)]
    # These fields are not set as annotations because it turns off syntax highlighting for the lambda in some editors.
    extension: str = Field(
        default_factory=lambda data: re.sub(r"[^a-zA-Z0-9_-]", "", data["name"].lower()),
        pattern=r"^[a-zA-Z0-9_-]+$",
        validate_default=True,
    )
    tagDisplayName: str = Field(
        default_factory=lambda data: re.sub(r"[^a-zA-Z0-9_\-.]", "-", data["name"].lower()),
        pattern=r"^[a-zA-Z0-9_.-]+$",
        validate_default=True,
    )


class ImageVersion(BakeryPathMixin, BakeryYAMLModel):
    parent: Annotated[Union[BakeryYAMLModel, None], Field(exclude=True, default=None)]
    name: str
    subpath: Annotated[str, Field(default_factory=lambda data: data["name"])]
    registries: Annotated[list[Registry], Field(default_factory=list)]
    latest: Annotated[bool, Field(default=False)]
    os: Annotated[list[ImageVersionOS], Field(default_factory=list)]

    @model_validator(mode="after")
    def resolve_parentage(self) -> Self:
        for version_os in self.os:
            version_os.parent = self
        return self

    @computed_field
    @property
    def path(self) -> Path:
        """Returns the path to the image version directory."""
        if self.parent is None or self.parent.path is None:
            raise ValueError("Parent image must resolve a valid path.")
        return Path(self.parent.path) / self.subpath

    @computed_field
    @property
    def merged_registries(self) -> list[Registry]:
        """Returns the merged registries for this image version."""
        all_registries = deepcopy(self.registries)
        if self.parent is not None and isinstance(self.parent, Image):
            for registry in self.parent.merged_registries:
                if registry not in all_registries:
                    all_registries.append(registry)
        return all_registries


class ImageVariant(BakeryYAMLModel):
    parent: Annotated[Union[BakeryYAMLModel, None] | None, Field(exclude=True, default=None)]
    name: str
    extension: str = Field(
        default_factory=lambda data: re.sub(r"[^a-zA-Z0-9_-]", "", data["name"].lower()),
        pattern=r"^[a-zA-Z0-9_-]+$",
        validate_default=True,
    )
    tagDisplayName: str = Field(
        default_factory=lambda data: re.sub(r"[^a-zA-Z0-9_\-.]", "-", data["name"].lower()),
        pattern=r"^[a-zA-Z0-9_.-]+$",
        validate_default=True,
    )
    tagPatterns: Annotated[list[TagPattern], Field(default_factory=list)]
    options: Annotated[list[ToolField], Field(default_factory=default_tool_options)]


def default_image_variants() -> list[ImageVariant]:
    return [
        ImageVariant(name="Standard", extension="std", tagDisplayName="std"),
        ImageVariant(name="Minimal", extension="min", tagDisplayName="min"),
    ]


class Image(BakeryPathMixin, BakeryYAMLModel):
    parent: Annotated[Union[BakeryYAMLModel, None] | None, Field(exclude=True, default=None)]
    name: str
    subpath: Annotated[str, Field(default_factory=lambda data: data["name"])]
    registries: Annotated[list[Registry], Field(default_factory=list)]
    tagPatterns: Annotated[list[TagPattern], Field(default_factory=default_tag_patterns)]
    variants: Annotated[list[ImageVariant], Field(default_factory=default_image_variants)]
    versions: Annotated[list[ImageVersion], Field(default_factory=list)]

    @field_validator("versions", mode="after")
    @classmethod
    def check_version_duplicates(cls, versions: list[ImageVersion]) -> list[ImageVersion]:
        """Ensures that there are no duplicate version names in the image."""
        error_message = ""
        seen_names = set()
        for version in versions:
            if version.name in seen_names:
                if not error_message:
                    error_message = "Duplicate versions found:\n"
                error_message += f" - {version.name}\n"
            seen_names.add(version.name)
        if error_message:
            raise ValueError(error_message.strip())
        return versions

    @field_validator("variants", mode="after")
    @classmethod
    def check_variant_duplicates(cls, variants: list[ImageVariant]) -> list[ImageVariant]:
        """Ensures that there are no duplicate variant names in the image."""
        error_message = ""
        seen_names = set()
        for variant in variants:
            if variant.name in seen_names:
                if not error_message:
                    error_message = "Duplicate variants found:\n"
                error_message += f" - {variant.name}\n"
            seen_names.add(variant.name)
        if error_message:
            raise ValueError(error_message.strip())
        return variants

    @model_validator(mode="after")
    def resolve_parentage(self) -> Self:
        for variant in self.variants:
            variant.parent = self
        for version in self.versions:
            version.parent = self
            for os in version.os:
                os.parent = version
        return self

    @computed_field
    @property
    def path(self) -> Path | None:
        """Returns the path to the image directory."""
        if self.parent is None or self.parent.path is None:
            raise ValueError("Parent BakeryConfig must resolve a valid path.")
        return Path(self.parent.path) / self.subpath

    @computed_field
    @property
    def merged_registries(self) -> list[Registry]:
        """Returns the merged registries for this image."""
        all_registries = deepcopy(self.registries)
        if self.parent is not None:
            for registry in self.parent.registries:
                if registry not in all_registries:
                    all_registries.append(registry)
        return all_registries

    def get_version(self, name: str) -> ImageVersion | None:
        """Returns an image version by name, or None if not found."""
        for version in self.versions:
            if version.name == name:
                return version
        return None

    def create_version(
        self,
        version: str,
        subpath: str | None = None,
        latest: bool = True,
        update_if_exists: bool = False,
    ) -> ImageVersion:
        """Creates a new image version and adds it to the image."""
        # Check if the version already exists
        existing_version = self.get_version(version)
        # If it exists and update_if_exists is False, raise an error.
        if existing_version and not update_if_exists:
            raise ValueError(f"Version '{version}' already exists in image '{self.name}'.")

        # Logic for creating a new version.
        if existing_version is None:
            # Copy the latest OS and registries if they exist and unset latest on all other versions.
            os = None
            registries = None
            for v in self.versions:
                if v.latest:
                    if v.os:
                        os = deepcopy(v.os)
                    if v.registries:
                        registries = deepcopy(v.registries)
                v.latest = False

            # Setup the arguments for the new version. Leave out fields that are None so they are defaulted.
            args = {"name": version, "parent": self}
            if subpath is not None:
                args["subpath"] = subpath
            if os is not None:
                args["os"] = os
            if registries is not None:
                args["registries"] = registries

            new_version = ImageVersion(**args)
            self.versions.append(new_version)
            return new_version

        # Logic for updating an existing version.
        else:
            if latest:
                # Unset latest on all other versions and set this one to latest.
                for v in self.versions:
                    v.latest = False
                existing_version.latest = True
            if subpath:
                existing_version.subpath = subpath
            return existing_version
