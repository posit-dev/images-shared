import logging
import re
from copy import deepcopy
from pathlib import Path
from typing import Annotated, Self, Union

from pydantic import BaseModel, Field, model_validator, computed_field, field_validator, HttpUrl
from pydantic_core.core_schema import ValidationInfo

from posit_bakery.config.registry import Registry
from posit_bakery.config.shared import BakeryPathMixin, BakeryYAMLModel
from posit_bakery.config.tag import TagPattern, default_tag_patterns
from posit_bakery.config.tools import ToolField, default_tool_options


log = logging.getLogger(__name__)


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

    def __hash__(self):
        """Unique hash for an ImageVersionOS object."""
        return hash((self.name, self.extension, self.tagDisplayName))

    def __eq__(self, other):
        """Equality check for ImageVersionOS based on name."""
        if isinstance(other, ImageVersionOS):
            return hash(self) == hash(other)
        return False


class ImageVersion(BakeryPathMixin, BakeryYAMLModel):
    parent: Annotated[Union[BakeryYAMLModel, None], Field(exclude=True, default=None)]
    name: str
    subpath: Annotated[str, Field(default_factory=lambda data: data["name"])]
    registries: Annotated[list[Registry], Field(default_factory=list)]
    overrideRegistries: Annotated[list[Registry], Field(default_factory=list)]
    latest: Annotated[bool, Field(default=False)]
    os: Annotated[list[ImageVersionOS], Field(default_factory=list, validate_default=True)]

    @field_validator("registries", "overrideRegistries", mode="after")
    @classmethod
    def deduplicate_registries(cls, registries: list[Registry], info: ValidationInfo) -> list[Registry]:
        """Ensures that the registries list is unique and warns on duplicates."""
        unique_registries = set(registries)
        for unique_registry in unique_registries:
            if registries.count(unique_registry) > 1:
                log.warning(
                    f"Duplicate registry defined in config for version '{info.data['name']}': "
                    f"{unique_registry.base_url}"
                )
        return list(unique_registries)

    @field_validator("os", mode="after")
    @classmethod
    def check_os_not_empty(cls, os: list[ImageVersionOS], info: ValidationInfo) -> list[ImageVersionOS]:
        """Ensures that the os list is not empty."""
        if not os:
            log.warning(
                f"No OSes defined for image version '{info.data['name']}'. At least one OS should be defined for "
                f"complete tagging and labeling of images."
            )
        return os

    @field_validator("os", mode="after")
    @classmethod
    def deduplicate_os(cls, os: list[ImageVersionOS], info: ValidationInfo) -> list[ImageVersionOS]:
        """Ensures that the os list is unique and warns on duplicates."""
        unique_oses = set(os)
        for unique_os in unique_oses:
            if os.count(unique_os) > 1:
                log.warning(f"Duplicate OS defined in config for image version '{info.data['name']}': {unique_os.name}")
        return list(unique_oses)

    @field_validator("os", mode="after")
    @classmethod
    def make_single_os_primary(cls, os: list[ImageVersionOS], info: ValidationInfo) -> list[ImageVersionOS]:
        """Ensures that at most one OS is marked as primary."""
        if len(os) == 1:
            # If there's only one OS, mark it as primary by default.
            log.info(
                f"Only one OS, {os[0].name}, defined for image version {info.data['name']}. Marking it as primary OS."
            )
            os[0].primary = True
        return os

    @field_validator("os", mode="after")
    @classmethod
    def max_one_primary_os(cls, os: list[ImageVersionOS], info: ValidationInfo) -> list[ImageVersionOS]:
        """Ensures that at most one OS is marked as primary."""
        primary_os_count = sum(1 for o in os if o.primary)
        if primary_os_count > 1:
            raise ValueError(
                f"Only one OS can be marked as primary for image version '{info.data['name']}'. "
                f"Found {primary_os_count} OSes marked primary."
            )
        elif primary_os_count == 0:
            log.warning(
                f"No OS marked as primary for image version '{info.data['name']}'. "
                "At least one OS should be marked as primary for complete tagging and labeling of images."
            )
        return os

    @model_validator(mode="after")
    def registries_or_override_registries(self) -> Self:
        """Ensures that only one of registries or overrideRegistries is defined."""
        if self.registries and self.overrideRegistries:
            raise ValueError(
                f"Only one of 'registries' or 'overrideRegistries' can be defined for image version '{self.name}'."
            )
        return self

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
    def all_registries(self) -> list[Registry]:
        """Returns the merged registries for this image version."""
        # If overrideRegistries are set, return those directly.
        if self.overrideRegistries:
            return deepcopy(self.overrideRegistries)

        # Otherwise, merge the registries from the image version and its parent.
        all_registries = deepcopy(self.registries)
        if self.parent is not None and isinstance(self.parent, Image):
            for registry in self.parent.all_registries:
                if registry not in all_registries:
                    all_registries.append(registry)

        return all_registries


class ImageVariant(BakeryYAMLModel):
    parent: Annotated[Union[BakeryYAMLModel, None] | None, Field(exclude=True, default=None)]
    name: str
    primary: Annotated[bool, Field(default=False)]
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

    def __hash__(self):
        """Unique hash for an ImageVariant object."""
        return hash((self.name, self.extension, self.tagDisplayName))


def default_image_variants() -> list[ImageVariant]:
    return [
        ImageVariant(name="Standard", extension="std", tagDisplayName="std", primary=True),
        ImageVariant(name="Minimal", extension="min", tagDisplayName="min"),
    ]


class Image(BakeryPathMixin, BakeryYAMLModel):
    parent: Annotated[Union[BakeryYAMLModel, None] | None, Field(exclude=True, default=None)]
    name: str
    displayName: Annotated[str, Field(default_factory=lambda data: data["name"].replace("-", " ").title())]
    description: Annotated[str | None, Field(default=None)]
    documentationUrl: Annotated[HttpUrl | None, Field(default=None)]
    subpath: Annotated[str, Field(default_factory=lambda data: data["name"])]
    registries: Annotated[list[Registry], Field(default_factory=list, validate_default=True)]
    overrideRegistries: Annotated[list[Registry], Field(default_factory=list, validate_default=True)]
    tagPatterns: Annotated[list[TagPattern], Field(default_factory=default_tag_patterns, validate_default=True)]
    variants: Annotated[list[ImageVariant], Field(default_factory=default_image_variants, validate_default=True)]
    versions: Annotated[list[ImageVersion], Field(default_factory=list, validate_default=True)]

    @field_validator("registries", "overrideRegistries", mode="after")
    @classmethod
    def deduplicate_registries(cls, registries: list[Registry], info: ValidationInfo) -> list[Registry]:
        """Ensures that the registries list is unique and warns on duplicates."""
        unique_registries = set(registries)
        for unique_registry in unique_registries:
            if registries.count(unique_registry) > 1:
                log.warning(
                    f"Duplicate registry defined in config for image '{info.data['name']}': {unique_registry.base_url}"
                )
        return list(unique_registries)

    @model_validator(mode="after")
    def registries_or_override_registries(self) -> Self:
        """Ensures that only one of registries or overrideRegistries is defined."""
        if self.registries and self.overrideRegistries:
            raise ValueError(
                f"Only one of 'registries' or 'overrideRegistries' can be defined for image '{self.name}'."
            )
        return self

    @field_validator("versions", mode="after")
    @classmethod
    def check_versions_not_empty(cls, versions: list[ImageVersion], info: ValidationInfo) -> list[ImageVersion]:
        """Ensures that the versions list is not empty."""
        if not versions:
            log.warning(
                f"No versions found in image '{info.data['name']}'. At least one version is required for most commands."
            )
        return versions

    @field_validator("versions", mode="after")
    @classmethod
    def check_version_duplicates(cls, versions: list[ImageVersion], info: ValidationInfo) -> list[ImageVersion]:
        """Ensures that there are no duplicate version names in the image."""
        error_message = ""
        seen_names = set()
        for version in versions:
            if version.name in seen_names:
                if not error_message:
                    error_message = f"Duplicate versions found in image '{info.data['name']}':\n"
                error_message += f" - {version.name}\n"
            seen_names.add(version.name)
        if error_message:
            raise ValueError(error_message.strip())
        return versions

    @field_validator("variants", mode="after")
    @classmethod
    def check_variant_duplicates(cls, variants: list[ImageVariant], info: ValidationInfo) -> list[ImageVariant]:
        """Ensures that there are no duplicate variant names in the image."""
        error_message = ""
        seen_names = set()
        for variant in variants:
            if variant.name in seen_names:
                if not error_message:
                    error_message = f"Duplicate variants found in image '{info.data['name']}':\n"
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
    def all_registries(self) -> list[Registry]:
        """Returns the merged registries for this image."""
        # If overrideRegistries are set, return those directly.
        if self.overrideRegistries:
            return deepcopy(self.overrideRegistries)

        # Otherwise, merge the registries from the image and its parent.
        all_registries = deepcopy(self.registries)
        if self.parent is not None:
            for registry in self.parent.all_registries:
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
