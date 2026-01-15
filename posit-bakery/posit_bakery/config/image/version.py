import logging
from typing import Annotated, Union

from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from posit_bakery.config.dependencies import DependencyVersionsField
from posit_bakery.config.mixins import (
    AllRegistriesMixin,
    OSParentageMixin,
    SubpathMixin,
    SupportedPlatformsMixin,
)
from posit_bakery.config.registry import BaseRegistry
from posit_bakery.config.registry import Registry
from posit_bakery.config.shared import BakeryPathMixin, BakeryYAMLModel
from posit_bakery.config.validators import (
    OSValidationMixin,
    RegistryValidationMixin,
    check_duplicates_or_raise,
)
from .version_os import ImageVersionOS

log = logging.getLogger(__name__)


class ImageVersion(
    OSValidationMixin,
    RegistryValidationMixin,
    SubpathMixin,
    SupportedPlatformsMixin,
    AllRegistriesMixin,
    OSParentageMixin,
    BakeryPathMixin,
    BakeryYAMLModel,
):
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
