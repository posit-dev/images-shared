import abc
from typing import Annotated, Union

from pydantic import Field, field_validator

from posit_bakery.config.shared import BakeryYAMLModel


class VersionsConstraint(BakeryYAMLModel):
    """Define versions using a constraint."""

    count: Annotated[
        int | None, Field(default=1, gt=0, description="Number of versions to include. Must be greater than 0.")
    ]
    latest: Annotated[bool | None, Field(description="Include the latest version.")]


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
        if not versions:
            raise ValueError("Versions list cannot be empty.")

        return versions

    @field_validator("versions", mode="after")
    def validate_versions_constraint(cls, versions: VersionsConstraint) -> VersionsConstraint:
        """Ensure that the versions constraint is valid."""

        return versions
