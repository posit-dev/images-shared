import abc
import logging
from copy import deepcopy
from typing import Annotated, Self

from pydantic import Field, model_validator

from posit_bakery.config.image.build_os import DEFAULT_PLATFORMS
from posit_bakery.config.image.version import ImageVersion
from posit_bakery.config.image.version_os import ImageVersionOS
from posit_bakery.config.registry import BaseRegistry, Registry
from posit_bakery.config.shared import BakeryYAMLModel
from posit_bakery.config.validators import (
    OSValidationMixinNoContext,
    RegistryValidationMixinNoContext,
)

log = logging.getLogger(__name__)


class BaseImageDevelopmentVersion(
    OSValidationMixinNoContext, RegistryValidationMixinNoContext, BakeryYAMLModel, abc.ABC
):
    """Base class for tool options in the bakery configuration."""

    parent: Annotated[BakeryYAMLModel | None, Field(exclude=True, default=None, description="Parent Image object.")]
    sourceType: Annotated[
        str,
        Field(
            description="Type of source used to retrieve the primary artifact version and download URL. "
            "Overridden in subclasses as a unique discriminator field."
        ),
    ]
    extraRegistries: Annotated[
        list[Registry | BaseRegistry],
        Field(
            default_factory=list,
            description="List of additional registries to use for this image development version with registries "
            "defined globally or for the image.",
        ),
    ]
    overrideRegistries: Annotated[
        list[Registry | BaseRegistry],
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
    values: Annotated[
        dict[str, str],
        Field(
            default_factory=dict,
            validate_default=True,
            description="Arbitrary key-value pairs used in template rendering.",
        ),
    ]

    @model_validator(mode="after")
    def resolve_parentage(self) -> Self:
        """Sets the parent for all OSes in this image version."""
        for version_os in self.os:
            version_os.parent = self
        return self

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

    @abc.abstractmethod
    def get_version(self) -> str:
        """Retrieve the version string for this image development version.

        :return: The version string.
        """
        raise NotImplementedError("Subclasses must implement get_version method.")

    @abc.abstractmethod
    def get_url_by_os(self, generalize_architecture: bool = False) -> dict[str, str]:
        """Retrieve the URLs for each OS for this image development version.

        :return: A map of OS names to their corresponding URL strings.
        """
        raise NotImplementedError("Subclasses must implement get_url method.")

    @model_validator(mode="after")
    def add_os_url(self) -> "BaseImageDevelopmentVersion":
        """Add the URL to each OS in the os list.

        :return: The modified BaseImageDevelopmentVersion object.
        """
        for os_version in self.os:
            url_by_os = self.get_url_by_os(generalize_architecture=os_version.platforms != DEFAULT_PLATFORMS)
            os_version.artifactDownloadURL = url_by_os.get(os_version.name, "")

        return self

    def as_image_version(self):
        """Convert this development version to a standard image version."""
        return ImageVersion(
            name=self.get_version(),
            subpath=f".dev-{self.get_version()}".replace(" ", "-").lower(),
            parent=self.parent,
            extraRegistries=self.extraRegistries,
            overrideRegistries=self.overrideRegistries,
            os=self.os,
            values=self.values,
            latest=False,
            dependencies=self.parent.resolve_dependency_versions(),
            ephemeral=True,
            isDevelopmentVersion=True,
        )
