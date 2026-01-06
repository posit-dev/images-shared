import logging
from pathlib import Path
from typing import Annotated, Union, Self

from pydantic import Field, field_validator, model_validator
from pydantic_core.core_schema import ValidationInfo

from posit_bakery.config import Registry, BaseRegistry, ImageVersionOS
from posit_bakery.config.dependencies import DependencyVersionsField, DependencyConstraintField
from posit_bakery.config.image.build_os import TargetPlatform, DEFAULT_PLATFORMS
from posit_bakery.config.shared import BakeryPathMixin, BakeryYAMLModel

log = logging.getLogger(__name__)


class ImageMatrix(BakeryPathMixin, BakeryYAMLModel):
    """Model representing a matrix of a image value combinations to build."""

    parent: Annotated[
        Union[BakeryYAMLModel, None], Field(exclude=True, default=None, description="Parent Image object.")
    ]
    namePattern: Annotated[str, Field(description="A pattern to use for image names.")]
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
    os: Annotated[
        list[ImageVersionOS],
        Field(
            default_factory=list,
            validate_default=True,
            description="List of supported ImageVersionOS objects for this image version.",
        ),
    ]
    dependencyConstraints: Annotated[
        list[DependencyConstraintField],
        Field(
            default_factory=list,
            validate_default=True,
            description="Dependencies to install, specified by a version constraint.",
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
        dict[str, str],
        Field(
            default_factory=dict,
            validate_default=True,
            description="Arbitrary key-value pairs used in template rendering.",
        ),
    ]

    @field_validator("extraRegistries", "overrideRegistries", mode="after")
    @classmethod
    def deduplicate_registries(
        cls, registries: list[Registry | BaseRegistry], info: ValidationInfo
    ) -> list[Registry | BaseRegistry]:
        """Ensures that the registries list is unique and warns on duplicates.

        :param registries: List of registries to deduplicate.
        :param info: ValidationInfo containing the data being validated.

        :return: A list of unique registries.
        """
        unique_registries = set(registries)
        for unique_registry in unique_registries:
            if registries.count(unique_registry) > 1:
                log.warning(
                    f"Duplicate registry defined in config for version '{info.data.get('name')}': "
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
        if info.data.get("name") and not os:
            log.warning(
                f"No OSes defined for image version '{info.data['name']}'. At least one OS should be defined for "
                f"complete tagging and labeling of images."
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
            if info.data.get("name") and os.count(unique_os) > 1:
                log.warning(f"Duplicate OS defined in config for image version '{info.data['name']}': {unique_os.name}")

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
            if info.data.get("name") and not os[0].primary:
                log.info(
                    f"Only one OS, {os[0].name}, defined for image version {info.data['name']}. Marking it as primary "
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
                f"Only one OS can be marked as primary for image version '{info.data['name']}'. "
                f"Found {primary_os_count} OSes marked primary."
            )
        elif info.data.get("name") and primary_os_count == 0:
            log.warning(
                f"No OS marked as primary for image version '{info.data['name']}'. "
                "At least one OS should be marked as primary for complete tagging and labeling of images."
            )
        return os

    @field_validator("dependencyConstraints", mode="after")
    @classmethod
    def check_duplicate_dependency_constraints(
        cls, dependency_constraints: list[DependencyConstraintField], info: ValidationInfo
    ) -> list[DependencyConstraintField]:
        """Ensures that there are no duplicate dependencies in the image.

        :param dependency_constraints: List of DependencyConstraintField objects to check for duplicates.
        :param info: ValidationInfo containing the data being validated.

        :return: The unmodified list of DependencyConstraintField objects if no duplicates are found.

        :raises ValueError: If duplicate dependencies are found.
        """
        error_message = ""
        seen_dependencies = set()
        for dc in dependency_constraints:
            if dc.dependency in seen_dependencies:
                if not error_message:
                    error_message = f"Duplicate dependency constraints found in image '{info.data['name']}':\n"
                error_message += f" - {dc.dependency}\n"
            seen_dependencies.add(dc.dependency)
        if error_message:
            raise ValueError(error_message.strip())
        return dependency_constraints

    @field_validator("dependencies", mode="after")
    @classmethod
    def resolve_dependency_constraints_to_dependencies(
        cls, dependencies: list[DependencyVersionsField], info: ValidationInfo
    ) -> list[DependencyVersionsField]:
        """Resolves any DependencyConstraintField entries in dependencies to DependencyVersionsField entries.

        :param dependencies: List of dependencies to resolve.
        :param info: ValidationInfo containing the data being validated.

        :return: A list of DependencyVersionsField objects.
        """
        if info.data.get("dependencyConstraints"):
            for dc in info.data.get("dependencyConstraints"):
                dependencies.append(dc.resolve_versions())

        return dependencies

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
                    error_message = f"Duplicate dependency or dependency constraints found in image matrix':\n"
                error_message += f" - {d.dependency}\n"
            seen_dependencies.add(d.dependency)
        if error_message:
            raise ValueError(error_message.strip())
        return dependencies

    @property
    def path(self) -> Path | None:
        """Returns the path to the image version directory.

        :raises ValueError: If the parent image does not have a valid path.
        """
        if self.parent is None or self.parent.path is None:
            raise ValueError("Parent image must resolve a valid path.")
        return Path(self.parent.path) / Path(self.subpath)

    @model_validator(mode="after")
    def resolve_parentage(self) -> Self:
        """Sets the parent for all OSes in this image version."""
        for version_os in self.os:
            version_os.parent = self
        return self

    @property
    def supported_platforms(self) -> list[TargetPlatform]:
        """Returns a list of supported target platforms for this image version.
        :return: A list of TargetPlatform objects supported by this image version.
        """
        if not self.os:
            return DEFAULT_PLATFORMS

        platforms = []

        for version_os in self.os:
            for platform in version_os.platforms:
                if platform not in platforms:
                    platforms.append(platform)
        return platforms
