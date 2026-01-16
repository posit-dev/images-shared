import abc
import typing
from typing import Annotated, ClassVar

from pydantic import Field, field_validator, model_serializer, AliasChoices

from posit_bakery.config.shared import BakeryYAMLModel
from .version import DependencyVersion, VersionConstraint


class Dependency(BakeryYAMLModel, abc.ABC):
    """Base class for dependency options in the bakery configuration."""

    dependency: Annotated[str, Field(description="Name of the dependency. Set as a literal in subclasses.")]

    @abc.abstractmethod
    def available_versions(self) -> list[DependencyVersion]:
        """Return a list of available versions for the dependency."""


class DependencyVersions(BakeryYAMLModel):
    """Class for specifying a list of dependency versions."""

    versions: Annotated[
        list[str],
        Field(
            validation_alias=AliasChoices("versions", "version"),
            default_factory=list,
            validate_default=True,
            description="List of specific versions to include for the dependency.",
        ),
    ]

    @field_validator("versions", mode="before")
    def single_string_to_list(cls, v: str | list[str]) -> list[str]:
        """Convert a single string to a list."""
        if isinstance(v, str):
            # Allow comma-separated strings as well. A single version will convert to a single-item list this way too.
            return [x.strip() for x in v.split(",")]

        return v

    @field_validator("versions", mode="after")
    def validate_versions_list(cls, versions: list[str]) -> list[str]:
        """Ensure that a version list is valid."""
        if not versions:
            raise ValueError("Versions list cannot be empty.")

        return versions

    @model_serializer(mode="wrap")
    def serialize_versions(self, next_serializer):
        dumped = next_serializer(self)
        for name, field_info in self.model_fields.items():
            # Ensure Literal fields are always included since exclude_unset=True is used in serialization.
            if typing.get_origin(field_info.annotation) == typing.Literal:
                dumped[name] = getattr(self, name)
            # If there's only one version, serialize as a single string as "version" for convenience.
            if name == "versions" and len(self.versions) == 1:
                dumped["version"] = self.versions[0]
                dumped.pop("versions")
        return dumped


class DependencyConstraint(BakeryYAMLModel):
    """Class for specifying a list of dependency version constraints."""

    VERSIONS_CLASS: ClassVar[type[DependencyVersions]] = DependencyVersions
    constraint: Annotated[
        VersionConstraint,
        Field(
            default_factory=list,
            validate_default=True,
            description="Version constraints to apply for the dependency.",
        ),
    ]

    def resolve_versions(self) -> DependencyVersions:
        """Return a list of versions that satisfy the constraints.

        Each subclass must implement `available_versions`
        """
        return self.VERSIONS_CLASS(
            versions=[str(v) for v in self.constraint.resolve_versions(self.available_versions())]
        )

    @model_serializer(mode="wrap")
    def serialize_versions(self, next_serializer):
        dumped = next_serializer(self)
        for name, field_info in self.model_fields.items():
            # Ensure Literal fields are always included since exclude_unset=True is used in serialization.
            if typing.get_origin(field_info.annotation) == typing.Literal:
                dumped[name] = getattr(self, name)
        return dumped
