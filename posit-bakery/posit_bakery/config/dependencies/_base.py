import abc
from typing import Annotated, Union

from pydantic import Field, field_validator

from posit_bakery.config.shared import BakeryYAMLModel


class VersionsConstraint(BakeryYAMLModel):
    """Define versions using a constraint."""

    count: Annotated[
        int | None, Field(default=None, gt=0, description="Number of versions to include. Must be greater than 0.")
    ]
    latest: Annotated[bool | None, Field(default=None, description="Include the latest version.")]
    max: Annotated[str | None, Field(default=None, description="Maximum version to include.")]
    min: Annotated[str | None, Field(default=None, description="Minimum version to include.")]


class Dependency(BakeryYAMLModel, abc.ABC):
    """Base class for dependency options in the bakery configuration."""

    # dependency: Annotated[str, Field(description="Name of the dependency. Set as a literal in subclasses.")]
    versions: Annotated[
        list[str] | VersionsConstraint,
        Field(
            union_mode="left_to_right",
            description="Versions of the dependency. Can be a list of versions or a constraint defining how many "
            "versions to include.",
        ),
    ]

    @field_validator("versions", mode="after")
    def validate_versions_list(cls, versions: list[str]) -> list[str]:
        """Ensure that the versions field is either a list or a constraint."""
        if not isinstance(versions, list):
            return versions

        if not versions:
            raise ValueError("Versions list cannot be empty.")

        return versions

    @field_validator("versions", mode="after")
    def validate_versions_constraint_mutually_exclusive(cls, versions: VersionsConstraint) -> VersionsConstraint:
        """Ensure that the versions constraint is valid."""
        if not isinstance(versions, VersionsConstraint):
            return versions

        if versions.latest is not None:
            if versions.max is not None:
                raise ValueError("Cannot specify both 'latest' and 'max' in versions constraint.")
            if versions.min is not None:
                raise ValueError("Cannot specify both 'latest' and 'min' in versions constraint.")

        if versions.count is not None:
            if versions.max is not None and versions.min is not None:
                raise ValueError("Cannot specify 'count' with both 'max' and 'min' in versions constraint.")

        return versions
