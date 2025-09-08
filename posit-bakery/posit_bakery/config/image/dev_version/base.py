import abc
import logging
from copy import deepcopy
from pathlib import Path
from typing import Annotated, Self

from pydantic import Field, field_validator, model_validator
from pydantic_core.core_schema import ValidationInfo

from posit_bakery.config import ImageVersion
from posit_bakery.config.registry import Registry
from posit_bakery.config.image.version_os import ImageVersionOS
from posit_bakery.config.shared import BakeryYAMLModel

log = logging.getLogger(__name__)


class BaseImageDevelopmentVersion(BakeryYAMLModel, abc.ABC):
    """Base class for tool options in the bakery configuration."""

    parent: Annotated[BakeryYAMLModel | None, Field(exclude=True, default=None, description="Parent Image object.")]
    sourceType: Annotated[str, Field(description="Type of source used to retrieve the version.")]
    extraRegistries: Annotated[
        list[Registry],
        Field(
            default_factory=list,
            description="List of additional registries to use for this image version with registries defined "
            "globally or for the image.",
        ),
    ]
    overrideRegistries: Annotated[
        list[Registry],
        Field(
            default_factory=list,
            description="List of registries to use in place of registries defined globally or for the image.",
        ),
    ]
    os: Annotated[
        list[ImageVersionOS],
        Field(
            default_factory=list,
            validate_default=True,
            description="List of supported ImageVersionOS objects for this image development version.",
        ),
    ]

    @field_validator("extraRegistries", "overrideRegistries", mode="after")
    @classmethod
    def deduplicate_registries(cls, registries: list[Registry], info: ValidationInfo) -> list[Registry]:
        """Ensures that the registries list is unique and warns on duplicates.

        :param registries: List of registries to deduplicate.
        :param info: ValidationInfo containing the data being validated.

        :return: A list of unique registries.
        """
        unique_registries = set(registries)
        for unique_registry in unique_registries:
            if registries.count(unique_registry) > 1:
                log.warning(
                    f"Duplicate registry defined in config for version '{info.data.get('_name')}': "
                    f"{unique_registry.base_url}"
                )
        return sorted(list(unique_registries), key=lambda r: r.base_url)

    @field_validator("os", mode="after")
    @classmethod
    def check_os_not_empty(cls, os: list[ImageVersionOS], info: ValidationInfo) -> list[ImageVersionOS]:
        """Ensures that the os list is not empty.

        :param os: List of ImageVersionOS objects to check.
        :param info: ValidationInfo containing the data being validated.

        :return: The unmodified list of ImageVersionOS objects.
        """
        # Check that name is defined since it will already propagate a validation error if not.
        if info.data.get("_name") and not os:
            log.warning(
                f"No OSes defined for image development version '{info.data['_name']}'. At least one OS should be "
                "defined for complete tagging and labeling of images."
            )
        return os

    @field_validator("os", mode="after")
    @classmethod
    def deduplicate_os(cls, os: list[ImageVersionOS], info: ValidationInfo) -> list[ImageVersionOS]:
        """Ensures that the os list is unique and warns on duplicates.

        :param os: List of ImageVersionOS objects to deduplicate.
        :param info: ValidationInfo containing the data being validated.

        :return: A list of unique ImageVersionOS objects.
        """
        unique_oses = set(os)
        for unique_os in unique_oses:
            if info.data.get("_name") and os.count(unique_os) > 1:
                log.warning(
                    f"Duplicate OS defined in config for image development version '{info.data['_name']}': "
                    f"{unique_os.name}"
                )

        return sorted(list(unique_oses), key=lambda o: o.name)

    @field_validator("os", mode="after")
    @classmethod
    def make_single_os_primary(cls, os: list[ImageVersionOS], info: ValidationInfo) -> list[ImageVersionOS]:
        """Ensures that at most one OS is marked as primary.

        :param os: List of ImageVersionOS objects to check.
        :param info: ValidationInfo containing the data being validated.

        :return: The list of ImageVersionOS objects with at most one primary OS.
        """
        # If there's only one OS, mark it as primary by default.
        if len(os) == 1:
            # Skip warning if name already propagates an error.
            if info.data.get("_name") and not os[0].primary:
                log.info(
                    f"Only one OS, {os[0].name}, defined for image version {info.data['_name']}. Marking it as primary "
                    f"OS."
                )
                os[0].primary = True

        return os

    @field_validator("os", mode="after")
    @classmethod
    def max_one_primary_os(cls, os: list[ImageVersionOS], info: ValidationInfo) -> list[ImageVersionOS]:
        """Ensures that at most one OS is marked as primary.

        :param os: List of ImageVersionOS objects to check.
        :param info: ValidationInfo containing the data being validated.

        :return: The list of ImageVersionOS objects with at most one primary OS.

        :raises ValueError: If more than one OS is marked as primary.
        """
        primary_os_count = sum(1 for o in os if o.primary)
        if primary_os_count > 1:
            raise ValueError(
                f"Only one OS can be marked as primary for image version '{info.data['_name']}'. "
                f"Found {primary_os_count} OSes marked primary."
            )
        elif info.data.get("_name") and primary_os_count == 0:
            log.warning(
                f"No OS marked as primary for image version '{info.data['_name']}'. "
                "At least one OS should be marked as primary for complete tagging and labeling of images."
            )

        return os

    @model_validator(mode="after")
    def extra_registries_or_override_registries(self) -> Self:
        """Ensures that only one of extraRegistries or overrideRegistries is defined.

        :raises ValueError: If both extraRegistries and overrideRegistries are defined.
        """
        if self.extraRegistries and self.overrideRegistries:
            raise ValueError(
                "Only one of 'extraRegistries' or 'overrideRegistries' can be defined for image version "
                f"'{self._name}'."
            )
        return self

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
    def all_registries(self) -> list[Registry]:
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

    @abc.abstractmethod
    def get_version(self) -> str:
        """Retrieve the version string for this image development version.

        :return: The version string.
        """
        raise NotImplementedError("Subclasses must implement get_version method.")

    @abc.abstractmethod
    def get_url_by_os(self) -> dict[str, str]:
        """Retrieve the URLs for each OS for this image development version.

        :return: A map of OS names to their corresponding URL strings.
        """
        raise NotImplementedError("Subclasses must implement get_url method.")

    def as_image_version(self):
        """Convert this development version to a standard image version."""
        os_urls = self.get_url_by_os()
        for _os in self.os:
            _os.downloadURL = os_urls.get(_os.name, "")
        return ImageVersion(
            name=self.get_version(),
            subpath=f".dev-{self.get_version()}".replace(" ", "-").lower(),
            parent=self.parent,
            extraRegistries=self.extraRegistries,
            overrideRegistries=self.overrideRegistries,
            os=self.os,
            latest=False,
            ephemeral=True,
        )
