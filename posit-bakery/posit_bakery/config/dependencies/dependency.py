import abc
from typing import Annotated, Union

from pydantic import Field, field_validator

from .version import DependencyVersion, VersionConstraint
from posit_bakery.config.shared import BakeryYAMLModel


class Dependency(BakeryYAMLModel, abc.ABC):
    """Base class for dependency options in the bakery configuration."""

    dependency: Annotated[str, Field(description="Name of the dependency. Set as a literal in subclasses.")]

    @abc.abstractmethod
    def available_versions(self) -> list[DependencyVersion]:
        """Return a list of available versions for the dependency."""
        raise NotImplementedError("Subclasses must implement the available_versions method.")


class DependencyConstraint(BakeryYAMLModel):
    """Class for specifying a list of dependency version constraints."""

    constraint: Annotated[
        VersionConstraint,
        Field(
            default_factory=list,
            validate_default=True,
            description="Version constraints to apply for the dependency.",
        ),
    ]


class DependencyVersions(BakeryYAMLModel):
    """Class for specifying a list of dependency versions."""

    versions: Annotated[
        list[str],
        Field(
            default_factory=list,
            validate_default=True,
            description="List of specific versions to include for the dependency.",
        ),
    ]

    @field_validator("versions", mode="after")
    def validate_versions_list(cls, versions: list[str]) -> list[str]:
        """Ensure that a version list is valid."""
        if not versions:
            raise ValueError("Versions list cannot be empty.")

        return versions
