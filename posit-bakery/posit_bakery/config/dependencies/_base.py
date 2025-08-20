import abc
from typing import Annotated, Union

from pydantic import Field, field_validator

from posit_bakery.config.shared import BakeryYAMLModel
from posit_bakery.config.dependencies.version import VersionConstraint


class Dependency(BakeryYAMLModel, abc.ABC):
    """Base class for dependency options in the bakery configuration."""

    # dependency: Annotated[str, Field(description="Name of the dependency. Set as a literal in subclasses.")]
    versions: Annotated[
        list[str] | VersionConstraint,
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
