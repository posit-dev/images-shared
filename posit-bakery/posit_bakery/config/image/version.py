import logging
from typing import Annotated, Any, Union, TYPE_CHECKING

from pydantic import Field, field_validator, model_validator
from pydantic_core.core_schema import ValidationInfo

from posit_bakery.config.dependencies import DependencyVersionsField
from posit_bakery.config.registry import BaseRegistry, Registry
from posit_bakery.config.shared import BakeryPathMixin, BakeryYAMLModel
from .variant import ImageVariant
from .version_matrix_base import VersionMatrixMixin
from .version_os import ImageVersionOS

if TYPE_CHECKING:
    from .image import Image

log = logging.getLogger(__name__)


class ImageVersion(VersionMatrixMixin, BakeryPathMixin, BakeryYAMLModel):
    """Model representing a version of an image."""

    # Fields are defined in the original order to maintain serialization compatibility
    parent: Annotated[
        Union["Image", None], Field(exclude=True, default=None, description="Parent Image object.")
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
    isMatrixVersion: Annotated[
        bool,
        Field(
            exclude=True,
            default=False,
            description="Flag to indicate if this is a matrix version.",
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
        dict[str, Any],
        Field(
            default_factory=dict,
            validate_default=True,
            description="Arbitrary key-value pairs used in template rendering.",
        ),
    ]

    @classmethod
    def _get_entity_name(cls) -> str:
        """Returns a human-readable name for this entity type."""
        return "image version"

    def _get_version_identifier(self) -> str:
        """Returns the version identifier for error messages."""
        return self.name

    def _get_image_template_values(self) -> dict[str, Any]:
        """Returns image-specific template values to add to the Image dict."""
        return {"Version": self.name, "IsDevelopmentVersion": self.isDevelopmentVersion}

    @model_validator(mode="before")
    @classmethod
    def log_duplicates_before_dedup(cls, data: dict) -> dict:
        """Log duplicate registries and OSes before they are deduplicated."""
        name = data.get("name")
        if not name:
            return data

        # Check for duplicate registries
        extra_registries = data.get("extraRegistries", [])
        override_registries = data.get("overrideRegistries", [])
        seen = set()
        for reg in extra_registries + override_registries:
            if isinstance(reg, dict):
                key = (reg.get("host"), reg.get("namespace"), reg.get("repository"))
                base_url = f"{reg.get('host')}/{reg.get('namespace')}"
                if reg.get("repository"):
                    base_url += f"/{reg.get('repository')}"
            else:
                key = (getattr(reg, "host", None), getattr(reg, "namespace", None), getattr(reg, "repository", None))
                base_url = reg.base_url if hasattr(reg, "base_url") else f"{key[0]}/{key[1]}"
            if key in seen:
                log.warning(f"Duplicate registry defined in config for version '{name}': {base_url}")
            seen.add(key)

        # Check for duplicate OSes
        os_list = data.get("os", [])
        seen_os = set()
        for os_item in os_list:
            if isinstance(os_item, dict):
                os_name = os_item.get("name")
            else:
                os_name = getattr(os_item, "name", None)
            if os_name in seen_os:
                log.warning(f"Duplicate OS defined in config for image version '{name}': {os_name}")
            seen_os.add(os_name)

        return data

    @field_validator("extraRegistries", "overrideRegistries", mode="after")
    @classmethod
    def deduplicate_registries(
        cls, registries: list[Registry | BaseRegistry]
    ) -> list[Registry | BaseRegistry]:
        """Ensures that the registries list is unique.

        :param registries: List of registries to deduplicate.

        :return: A list of unique registries.
        """
        return sorted(list(set(registries)), key=lambda r: r.base_url)

    @field_validator("os", mode="after")
    @classmethod
    def deduplicate_os(cls, os: list[ImageVersionOS]) -> list[ImageVersionOS]:
        """Ensures that the os list is unique.

        :param os: List of ImageVersionOS objects to deduplicate.

        :return: A list of unique ImageVersionOS objects.
        """
        return sorted(list(set(os)), key=lambda o: o.name)

    @field_validator("os", mode="after")
    @classmethod
    def make_single_os_primary(cls, os: list[ImageVersionOS]) -> list[ImageVersionOS]:
        """Ensures that if only one OS is defined, it is marked as primary.

        :param os: List of ImageVersionOS objects to check.

        :return: The list of ImageVersionOS objects with single OS marked primary.
        """
        if len(os) == 1:
            os[0].primary = True
        return os

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
        error_message = ""
        seen_dependencies = set()
        for d in dependencies:
            if d.dependency in seen_dependencies:
                if not error_message:
                    error_message = f"Duplicate dependencies found in image '{info.data.get('name')}':\n"
                error_message += f" - {d.dependency}\n"
            seen_dependencies.add(d.dependency)
        if error_message:
            raise ValueError(error_message.strip())
        return dependencies

    @model_validator(mode="after")
    def validate_os_settings(self) -> "ImageVersion":
        """Validate OS settings after all fields are available."""
        # Check if OS list is empty
        if not self.os:
            log.warning(
                f"No OSes defined for image version '{self.name}'. At least one OS should be defined for "
                f"complete tagging and labeling of images."
            )
            return self

        # Check primary OS count
        primary_os_count = sum(1 for o in self.os if o.primary)
        if primary_os_count > 1:
            raise ValueError(
                f"Only one OS can be marked as primary for image version '{self.name}'. "
                f"Found {primary_os_count} OSes marked primary."
            )
        elif primary_os_count == 0:
            log.warning(
                f"No OS marked as primary for image version '{self.name}'. "
                "At least one OS should be marked as primary for complete tagging and labeling of images."
            )

        return self

    @model_validator(mode="after")
    def extra_registries_or_override_registries(self) -> "ImageVersion":
        """Ensures that only one of extraRegistries or overrideRegistries is defined.

        :raises ValueError: If both extraRegistries and overrideRegistries are defined.
        """
        if self.extraRegistries and self.overrideRegistries:
            raise ValueError(
                f"Only one of 'extraRegistries' or 'overrideRegistries' can be defined for "
                f"image version '{self.name}'."
            )
        return self

    @model_validator(mode="after")
    def resolve_parentage(self) -> "ImageVersion":
        """Sets the parent for all OSes in this image version."""
        for version_os in self.os:
            version_os.parent = self
        return self

    def generate_template_values(
        self,
        variant: Union["ImageVariant", None] = None,
        version_os: Union["ImageVersionOS", None] = None,
    ) -> dict[str, Any]:
        """Generates the template values for rendering.

        :param variant: The ImageVariant object.
        :param version_os: The ImageVersionOS object, if applicable.

        :return: A dictionary of values to use for rendering version templates.
        """
        values = super().generate_template_values(variant, version_os)
        values["Dependencies"] = {d.dependency: d.versions for d in self.dependencies}
        return values
