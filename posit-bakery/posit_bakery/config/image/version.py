import logging
from copy import deepcopy
from pathlib import Path
from typing import Annotated, Union, Self

from pydantic import Field, field_validator, model_validator
from pydantic_core.core_schema import ValidationInfo

from posit_bakery.config.dependencies import DependencyVersionsField
from posit_bakery.config.registry import BaseRegistry
from posit_bakery.config.registry import Registry
from posit_bakery.config.shared import BakeryPathMixin, BakeryYAMLModel
from posit_bakery.config.validators import (
    OSValidationMixin,
    RegistryValidationMixin,
    check_duplicates_or_raise,
)
from .build_os import DEFAULT_PLATFORMS, TargetPlatform
from .version_os import ImageVersionOS

log = logging.getLogger(__name__)


class ImageVersion(OSValidationMixin, RegistryValidationMixin, BakeryPathMixin, BakeryYAMLModel):
    """Model representing a version of an image."""

    parent: Annotated[
        Union[BakeryYAMLModel, None], Field(exclude=True, default=None, description="Parent Image object.")
    ]
    name: Annotated[str, Field(description="The full image version.")]
    subpath: Annotated[
        str,
        Field(
            default_factory=lambda data: data.get("name", "").replace(" ", "-").lower(),
            min_length=1,
            description="Subpath under the image to use for the image version.",
        ),
    ]
    extraRegistries: Annotated[
        list[Registry | BaseRegistry],
        Field(
            default_factory=list,
            description="List of additional registries to use for this image version with registries defined "
            "globally or for the image.",
        ),
    ]
    overrideRegistries: Annotated[
        list[Registry | BaseRegistry],
        Field(
            default_factory=list,
            description="List of registries to use in place of registries defined globally or for the image.",
        ),
    ]
    latest: Annotated[
        bool, Field(default=False, description="Flag to indicate if this is the latest version of the image.")
    ]
    ephemeral: Annotated[
        bool,
        Field(
            exclude=True,
            default=False,
            description="Flag to indicate if this is an ephemeral image version rendering. If enabled, the version "
            "will be rendered and deleted after each operation.",
        ),
    ]
    isDevelopmentVersion: Annotated[
        bool,
        Field(
            exclude=True,
            default=False,
            description="Flag to indicate if this is a development version.",
        ),
    ]
    os: Annotated[
        list[ImageVersionOS],
        Field(
            default_factory=list,
            validate_default=True,
            description="List of supported ImageVersionOS objects for this image version.",
        ),
    ]
    dependencies: Annotated[
        list[DependencyVersionsField],
        Field(
            default_factory=list,
            validate_default=True,
            description="Dependency to install, pinned to a list of versions.",
        ),
    ]
    values: Annotated[
        dict[str, str],
        Field(
            default_factory=dict,
            validate_default=True,
            description="Arbitrary key-value pairs used in template rendering.",
        ),
    ]

    @classmethod
    def _get_registry_context_type(cls) -> str:
        """Return the type name for messages."""
        return "image version"

    @field_validator("dependencies", mode="after")
    @classmethod
    def check_duplicate_dependencies(
        cls, dependencies: list[DependencyVersionsField], info: ValidationInfo
    ) -> list[DependencyVersionsField]:
        """Ensures that the dependencies list is unique and errors on duplicates.

        :param dependencies: List of dependencies to deduplicate.
        :param info: ValidationInfo containing the data being validated.

        :return: A list of unique dependencies.

        :raises ValueError: If duplicate dependencies are found.
        """

        def error_message_func(dupes: list) -> str:
            msg = f"Duplicate dependencies found in image '{info.data['name']}':\n"
            msg += "".join(f" - {d}\n" for d in dupes)
            return msg.strip()

        return check_duplicates_or_raise(
            dependencies,
            key_func=lambda d: d.dependency,
            error_message_func=error_message_func,
        )

    @model_validator(mode="after")
    def resolve_parentage(self) -> Self:
        """Sets the parent for all OSes in this image version."""
        for version_os in self.os:
            version_os.parent = self
        return self

    @property
    def path(self) -> Path | None:
        """Returns the path to the image version directory.

        :raises ValueError: If the parent image does not have a valid path.
        """
        if self.parent is None or self.parent.path is None:
            raise ValueError("Parent image must resolve a valid path.")
        return Path(self.parent.path) / Path(self.subpath)

    @property
    def all_registries(self) -> list[Registry | BaseRegistry]:
        """Returns the merged registries for this image version.

        :return: A list of registries that includes the overrideRegistiries or the version's extraRegistries and any
            registries from the parent image.
        """
        # If overrideRegistries are set, return those directly.
        if self.overrideRegistries:
            return deepcopy(self.overrideRegistries)

        # Otherwise, merge the registries from the image version and its parent.
        all_registries = deepcopy(self.extraRegistries)
        if self.parent is not None:
            for registry in self.parent.all_registries:
                if registry not in all_registries:
                    all_registries.append(registry)

        return all_registries

    @property
    def supported_platforms(self) -> list[TargetPlatform]:
        """Returns a list of supported target platforms for this image version.
        :return: A list of TargetPlatform objects supported by this image version.
        """
        if not self.os:
            return DEFAULT_PLATFORMS

        platforms = []

        for version_os in self.os:
            for platform in version_os.platforms:
                if platform not in platforms:
                    platforms.append(platform)
        return platforms
