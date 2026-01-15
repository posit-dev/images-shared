import itertools
import logging
from typing import Annotated, Any, Union

from pydantic import Field, field_validator, model_validator
from pydantic_core.core_schema import ValidationInfo

from posit_bakery.config.dependencies import (
    DependencyVersionsField,
    DependencyConstraintField,
    get_dependency_versions_class,
    DependencyVersions,
)
from posit_bakery.config.mixins import OSParentageMixin, SubpathMixin, SupportedPlatformsMixin
from posit_bakery.config.registry import BaseRegistry, Registry
from posit_bakery.config.shared import BakeryPathMixin, BakeryYAMLModel
from posit_bakery.config.templating import jinja2_env
from posit_bakery.config.validators import (
    OSValidationMixin,
    RegistryValidationMixin,
    check_duplicates_or_raise,
)
from .version import ImageVersion
from .version_os import ImageVersionOS

log = logging.getLogger(__name__)


def generate_default_name_pattern(data: dict[str, Any]) -> str:
    """Generates the default name pattern for image versions.

    :return: The default name pattern string.
    """
    dependencies = data.get("dependencies", [])
    values = data.get("values", {})

    pattern = ""
    for dependency in dependencies:
        pattern += dependency.dependency + "{{ " + f"Dependencies.{dependency.dependency}" + " }}-"
    for key in sorted(values.keys()):
        pattern += key + "{{ " + f"Values.{key}" + " }}-"
    pattern = pattern.rstrip("-")

    if not pattern:
        raise ValueError("If no dependencies or values are defined, a namePattern must be explicitly set.")

    return pattern


class ImageMatrix(
    OSValidationMixin,
    RegistryValidationMixin,
    SubpathMixin,
    SupportedPlatformsMixin,
    OSParentageMixin,
    BakeryPathMixin,
    BakeryYAMLModel,
):
    """Factory for generating ImageVersion objects from a cartesian product of values.

    ImageMatrix is a pure factory that generates multiple ImageVersion objects
    by computing the cartesian product of dependency versions and custom values.
    The core method is `to_image_versions()` which produces the ImageVersion list.

    Matrix-specific fields (for cartesian product generation):
        - namePattern: Template for generating version names
        - values: Custom key-value pairs to expand
        - dependencies: Pinned dependency versions to expand
        - dependencyConstraints: Constraints that resolve to dependency versions

    Template fields (passed through to generated ImageVersions):
        - parent, subpath, os, extraRegistries, overrideRegistries

    Example:
        A matrix with dependencies=[python: [3.11, 3.12]] and values={variant: [full, min]}
        generates 4 ImageVersions: python3.11-full, python3.11-min, python3.12-full, python3.12-min
    """

    parent: Annotated[
        Union[BakeryYAMLModel, None], Field(exclude=True, default=None, description="Parent Image object.")
    ]
    subpath: Annotated[
        str,
        Field(
            default="matrix",
            min_length=1,
            description="Subpath under the image to use for the image version.",
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
        dict[str, str | list],
        Field(
            default_factory=dict,
            validate_default=True,
            description="Arbitrary key-value pairs used in template rendering.",
        ),
    ]
    namePattern: Annotated[
        str, Field(description="A pattern to use for image names.", default_factory=generate_default_name_pattern)
    ]
    os: Annotated[
        list[ImageVersionOS],
        Field(
            default_factory=list,
            validate_default=True,
            description="List of supported ImageVersionOS objects for this image version.",
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

    @classmethod
    def _get_os_context(cls, info: ValidationInfo | None) -> str | None:
        """Return context string for messages using namePattern."""
        if info is None:
            return None
        return info.data.get("namePattern") or None

    @classmethod
    def _get_os_context_type(cls) -> str:
        """Return the type name for messages."""
        return "image matrix with name pattern"

    @classmethod
    def _get_registry_context_type(cls) -> str:
        """Return the type name for messages."""
        return "image matrix with name pattern"

    @model_validator(mode="before")
    @classmethod
    def check_one_of_dependencies_or_values(cls, data) -> dict:
        """Ensures that at least one of dependencies or values is defined.

        :raises ValueError: If neither dependencies nor values are defined.
        """
        if not (data.get("dependencyConstraints") or data.get("dependencies")) and not data.get("values"):
            raise ValueError(
                "At least one of 'dependencies' or 'values' must be defined for an image matrix. Perhaps use normal "
                "image versions instead?"
            )

        return data

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

        def error_message_func(dupes: list) -> str:
            msg = "Duplicate dependency constraints found in image matrix:\n"
            msg += "".join(f" - {d}\n" for d in dupes)
            return msg.strip()

        return check_duplicates_or_raise(
            dependency_constraints,
            key_func=lambda dc: dc.dependency,
            error_message_func=error_message_func,
        )

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

        def error_message_func(dupes: list) -> str:
            msg = "Duplicate dependency or dependency constraints found in image matrix:\n"
            msg += "".join(f" - {d}\n" for d in dupes)
            return msg.strip()

        return check_duplicates_or_raise(
            dependencies,
            key_func=lambda d: d.dependency,
            error_message_func=error_message_func,
        )

    @staticmethod
    def _render_name_pattern(
        name_pattern: str, dependencies: list[DependencyVersionsField], values: dict[str, Any]
    ) -> str:
        """Renders the name pattern with the given dependencies and values.

        :param name_pattern: The name pattern to render.
        :param dependencies: List of DependencyVersionsField objects.
        :param values: Dictionary of values.

        :return: The rendered name string.
        """
        env = jinja2_env()
        template = env.from_string(name_pattern)
        rendered_name = template.render(
            Dependencies={d.dependency: d.versions[0] for d in dependencies},
            Values=values,
        )
        rendered_name = rendered_name.strip()
        rendered_name = rendered_name.strip("-._")  # Ensure no leading or trailing separators.

        return rendered_name

    @staticmethod
    def _flatten_dependencies(dependencies: list[DependencyVersionsField]) -> list[DependencyVersionsField]:
        """Flattens the dependency versions into a list of single-version DependencyVersionsField objects.

        :param dependencies: List of DependencyVersionsField objects.

        :return: A flattened list of DependencyVersionsField objects.
        """
        flattened = []
        for dependency in dependencies:
            dependency_version_class = get_dependency_versions_class(dependency.dependency)
            dependency_versions = []
            for version in dependency.versions:
                dependency_versions.append(
                    dependency_version_class(dependency=dependency.dependency, versions=[version])
                )
            flattened.append(dependency_versions)
        return flattened

    @staticmethod
    def _flatten_values(values: dict[str, Any]) -> list[dict[str, Any]]:
        """Flattens the values into a dictionary of lists.

        :param values: Dictionary of values.

        :return: A flattened dictionary of values.
        """
        flattened = []
        for key, value in values.items():
            if isinstance(value, list):
                flattened.append([{key: v} for v in value])
            else:
                flattened.append([{key: value}])

        return flattened

    @staticmethod
    def _cartesian_product(
        dependencies: list[DependencyVersionsField], values: dict[str, Any]
    ) -> list[dict[str, list | dict]]:
        """Generates the cartesian product of dependency versions and values.

        :param dependencies: List of DependencyVersionsField objects.
        :param values: Dictionary of values.

        :return: A tuple containing a list of dependency combinations and a dictionary of value combinations.
        """
        flattened_dependencies = ImageMatrix._flatten_dependencies(dependencies)
        flattened_values = ImageMatrix._flatten_values(values)

        products = itertools.product(*flattened_dependencies, *flattened_values)

        grouped_products = []
        for product in products:
            grouped = {"dependencies": [], "values": {}}
            for item in product:
                if isinstance(item, DependencyVersions):
                    grouped["dependencies"].append(item)
                elif isinstance(item, dict):
                    grouped["values"].update(item)
            grouped_products.append(grouped)

        return grouped_products

    def to_image_versions(self) -> list[ImageVersion]:
        """Generates ImageVersion objects for each combination of OS and dependency versions.

        :return: A list of ImageVersion objects.
        """
        image_versions = []

        products = self._cartesian_product(self.dependencies, self.values)
        for product in products:
            image_version = ImageVersion(
                parent=self.parent,
                name=self._render_name_pattern(self.namePattern, product["dependencies"], product["values"]),
                subpath=self.subpath,
                extraRegistries=self.extraRegistries,
                overrideRegistries=self.overrideRegistries,
                os=self.os,
                dependencies=product["dependencies"],
                values=product["values"],
            )
            image_versions.append(image_version)

        return image_versions
