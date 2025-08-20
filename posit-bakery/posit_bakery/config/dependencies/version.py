from typing import Annotated, Self
from packaging.version import Version

from pydantic import Field, model_validator

from posit_bakery.config.shared import BakeryYAMLModel


class DependencyVersion(Version):
    """A version class for dependencies that extends packaging's Version.

    We require this so we can properly handle versions that are specified that
    only include a major and minor version, such as "1.4".
    The packaging library treats this a "1.4.0".
    """

    has_minor: bool
    has_micro: bool

    def __init__(self, version: str):
        """Initialize the DepencencyVersion with a version string."""

        # Initialize the parent class to catch any version parsing errors.
        super().__init__(version)

        # Track how the version was specified
        parts = version.split(".")
        self.has_minor = len(parts) > 1
        self.has_micro = len(parts) > 2


class VersionConstraint(BakeryYAMLModel):
    """Define versions using a constraint."""

    count: Annotated[
        int | None, Field(default=None, gt=0, description="Number of versions to include. Must be greater than 0.")
    ]
    latest: Annotated[bool | None, Field(default=None, description="Include the latest version.")]
    max: Annotated[str | None, Field(default=None, description="Maximum version to include.")]
    min: Annotated[str | None, Field(default=None, description="Minimum version to include.")]

    @model_validator(mode="after")
    def validate_versions_constraint_mutually_exclusive(self) -> Self:
        """Ensure that the versions constraint is valid."""

        if self.latest is not None:
            if self.max is not None:
                raise ValueError("Cannot specify both 'latest' and 'max' in versions constraint.")
            if self.min is not None:
                raise ValueError("Cannot specify both 'latest' and 'min' in versions constraint.")

        if self.count is not None:
            if self.max is not None and self.min is not None:
                raise ValueError("Cannot specify 'count' with both 'max' and 'min' in versions constraint.")

        return self
