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
    def validate_minimum_required_fields(self) -> Self:
        """Ensure we have enough fields to calculate a list of versions."""

        if self.latest and all([f is None for f in [self.count, self.max, self.min]]):
            # Default to 1 version if latest is True and no other fields are set.
            self.count = 1
            return self

        if all([f is None for f in [self.latest, self.max]]):
            raise ValueError("Version constraint must specify 'latest' or 'max'.")

        return self

    @model_validator(mode="after")
    def validate_versions_constraint_mutually_exclusive(self) -> Self:
        """Ensure that the versions constraint is valid."""

        if self.latest is not None:
            if self.max is not None:
                raise ValueError("Cannot specify both 'latest' and 'max' in versions constraint.")

        if self.count is not None:
            if self.latest is not None and self.min is not None:
                raise ValueError("Cannot specify 'count' with both 'latest' and 'min' in versions constraint.")
            if self.max is not None and self.min is not None:
                raise ValueError("Cannot specify 'count' with both 'max' and 'min' in versions constraint.")

        return self

    @model_validator(mode="after")
    def validate_max_min(self) -> Self:
        """Ensure that the versions constraint has valid value combinations."""

        if self.max is not None and self.min is not None:
            max_version = DependencyVersion(self.max)
            min_version = DependencyVersion(self.min)
            if min_version > max_version:
                raise ValueError("Cannot specify 'min' that is greater than 'max' in version constraint.")

        return self

    def _filter_range(self, versions: list[DependencyVersion]) -> list[DependencyVersion]:
        """Filter the versions based on the min and max constraints.

        Since the python packaging library treats "1.4" as "1.4.0", we need to
        handle filtering differently based on how the min and max were specified.

        For max, we want to retain all the patch versions that match a given
        minor version if it does not have a micro version if the max was
        specified without a micro version. Similarly if, only a major version
        was specified, we want to retain all minor and patch versions that
        match the major version.

        :param versions: List of versions to filter.

        :return: List of versions that match the min and max constraints.
        """

        filtered_versions = versions

        if self.max is not None:
            max_ = DependencyVersion(self.max)
            filtered_versions = [
                v
                for v in filtered_versions
                if (not max_.has_minor and v.major == max_.major)
                or (not max_.has_micro and v.major == max_.major and v.minor == max_.minor)
                or v <= max_
            ]

        if self.min is not None:
            min_ = DependencyVersion(self.min)
            filtered_versions = [v for v in filtered_versions if v >= min_]

        return filtered_versions

    def _filter_minor(self, versions: list[DependencyVersion]) -> list[DependencyVersion]:
        """Filter the versions to only include the latest patch version for each minor version.

        :param versions: List of versions to filter.

        :return: List of versions that only include the latest patch version for each minor version.
        """

        # Ensure versions are sorted in descending order
        versions = sorted(versions, reverse=True)
        found = set()

        filtered_versions = []
        for v in versions:
            minor_id = (v.major, v.minor)
            if minor_id not in found:
                filtered_versions.append(v)
                found.add(minor_id)

        return filtered_versions

    def resolve_versions(self, available_versions: list[DependencyVersion]) -> list[DependencyVersion]:
        """Resolve the versions based on the constraint and available versions.

        :param available_versions: List of available versions to filter.

        :return: List of versions that match the constraint.
        """

        versions = sorted(available_versions, reverse=True)
        # Filter based on min and max
        versions = self._filter_range(versions)
        # Filter to the most recent patch version for each minor version
        versions = self._filter_minor(versions)

        if self.count is not None:
            versions = versions[: self.count]

        return versions
