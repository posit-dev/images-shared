import itertools
import logging
from copy import deepcopy
from typing import Annotated, Any, Literal, Union

from pydantic import Field, field_validator, model_validator
from pydantic_core.core_schema import ValidationInfo

from posit_bakery.config.dependencies import (
    DependencyConstraintField,
    DependencyVersions,
    DependencyVersionsField,
    get_dependency_versions_class,
)
from posit_bakery.config.registry import BaseRegistry, Registry
from posit_bakery.config.shared import BakeryPathMixin, BakeryYAMLModel
from posit_bakery.config.templating import jinja2_env
from .variant import ImageVariant
from .version import ImageVersion
from .version_matrix_base import VersionMatrixMixin
from .version_os import ImageVersionOS

log = logging.getLogger(__name__)

DEFAULT_MATRIX_SUBPATH: Literal["matrix"] = "matrix"


def generate_default_name_pattern(data: dict[str, Any]) -> str:
    """Generates the default name pattern for image versions.

    :return: The default name pattern string.
    """
    dependencies = data.get("dependencies", [])
    dependency_constraints = data.get("dependencyConstraints", [])
    values = data.get("values", {})

    pattern = ""
    for dependency in dependencies:
        # Handle both dict and object forms
        dep_name = dependency.get("dependency") if isinstance(dependency, dict) else dependency.dependency
        pattern += dep_name + "{{ " + f"Dependencies.{dep_name}" + " }}-"
    for dependency_constraint in dependency_constraints:
        # Handle both dict and object forms
        dc_name = dependency_constraint.get("dependency") if isinstance(dependency_constraint, dict) else dependency_constraint.dependency
        pattern += dc_name + "{{ " + f"Dependencies.{dc_name}" + " }}-"
    for key in sorted(values.keys()):
        pattern += key + "{{ " + f"Values.{key}" + " }}-"
    pattern = pattern.rstrip("-")

    if not pattern:
        raise ValueError("If no dependencies or values are defined, a namePattern must be explicitly set.")

    return pattern


class ImageMatrix(VersionMatrixMixin, BakeryPathMixin, BakeryYAMLModel):
    """Model representing a matrix of image value combinations to build."""

    # Fields are defined in order to maintain YAML serialization compatibility.
    # The expected serialization order is: subpath, dependencyConstraints, dependencies, os, etc.
    parent: Annotated[
        Union[BakeryYAMLModel, None], Field(exclude=True, default=None, description="Parent Image object.")
    ]
    namePattern: Annotated[
        str, Field(default="", description="A pattern to use for image names.")
    ]
    subpath: Annotated[
        str,
        Field(
            default=DEFAULT_MATRIX_SUBPATH,
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
    values: Annotated[
        dict[str, Any],
        Field(
            default_factory=dict,
            validate_default=True,
            description="Arbitrary key-value pairs used in template rendering.",
        ),
    ]

    @classmethod
    def _get_entity_name(cls) -> str:
        """Returns a human-readable name for this entity type."""
        return "image matrix"

    def _get_version_identifier(self) -> str:
        """Returns the version identifier for error messages."""
        return self.namePattern

    def _get_image_template_values(self) -> dict[str, Any]:
        """Returns image-specific template values to add to the Image dict."""
        return {}  # Matrix doesn't include Version or IsDevelopmentVersion

    @model_validator(mode="wrap")
    @classmethod
    def compute_default_name_pattern(cls, data, handler) -> "ImageMatrix":
        """Compute the default namePattern if not provided.

        Uses wrap mode to compute the default before validation and then
        remove namePattern from fields_set if it was computed (not explicitly provided).
        """
        # If data is already an ImageMatrix instance (e.g., from model_validate), just run handler
        if isinstance(data, ImageMatrix):
            return handler(data)

        # Track if user explicitly provided namePattern (data is a dict)
        user_provided_name_pattern = bool(data.get("namePattern"))

        # Compute default if not provided
        if not user_provided_name_pattern:
            data["namePattern"] = generate_default_name_pattern(data)

        # Run the rest of validation
        instance = handler(data)

        # If namePattern was computed (not user-provided), remove from fields_set
        # so it won't be serialized with exclude_unset=True
        if not user_provided_name_pattern and "namePattern" in instance.__pydantic_fields_set__:
            instance.__pydantic_fields_set__.discard("namePattern")

        return instance

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

    @model_validator(mode="before")
    @classmethod
    def log_duplicates_before_dedup(cls, data: dict) -> dict:
        """Log duplicate registries and OSes before they are deduplicated."""
        # For ImageMatrix, we need to compute the namePattern first to include it in the log message
        # Try to get the namePattern from data, or compute it
        name_pattern = data.get("namePattern")
        if not name_pattern:
            # Compute a temporary name pattern for logging purposes
            try:
                name_pattern = generate_default_name_pattern(data)
            except ValueError:
                # Can't compute name pattern, skip logging
                return data

        # Check for duplicate registries
        extra_registries = data.get("extraRegistries", [])
        override_registries = data.get("overrideRegistries", [])
        seen = set()
        for reg in extra_registries + override_registries:
            if isinstance(reg, dict):
                key = (reg.get("host"), reg.get("namespace"), reg.get("repository"))
                base_url = f"{reg.get('host')}/{reg.get('namespace')}"
                if reg.get("repository"):
                    base_url += f"/{reg.get('repository')}"
            else:
                key = (getattr(reg, "host", None), getattr(reg, "namespace", None), getattr(reg, "repository", None))
                base_url = reg.base_url if hasattr(reg, "base_url") else f"{key[0]}/{key[1]}"
            if key in seen:
                log.warning(
                    f"Duplicate registry defined in config for image matrix with name pattern "
                    f"'{name_pattern}': {base_url}"
                )
            seen.add(key)

        # Check for duplicate OSes
        os_list = data.get("os", [])
        seen_os = set()
        for os_item in os_list:
            if isinstance(os_item, dict):
                os_name = os_item.get("name")
            else:
                os_name = getattr(os_item, "name", None)
            if os_name in seen_os:
                log.warning(
                    f"Duplicate OS defined in config for image matrix with name pattern "
                    f"'{name_pattern}': {os_name}"
                )
            seen_os.add(os_name)

        return data

    @field_validator("extraRegistries", "overrideRegistries", mode="after")
    @classmethod
    def deduplicate_registries(
        cls, registries: list[Registry | BaseRegistry]
    ) -> list[Registry | BaseRegistry]:
        """Ensures that the registries list is unique.

        :param registries: List of registries to deduplicate.

        :return: A list of unique registries.
        """
        return sorted(list(set(registries)), key=lambda r: r.base_url)

    @field_validator("os", mode="after")
    @classmethod
    def deduplicate_os(cls, os: list[ImageVersionOS]) -> list[ImageVersionOS]:
        """Ensures that the os list is unique.

        :param os: List of ImageVersionOS objects to deduplicate.

        :return: A list of unique ImageVersionOS objects.
        """
        return sorted(list(set(os)), key=lambda o: o.name)

    @field_validator("os", mode="after")
    @classmethod
    def make_single_os_primary(cls, os: list[ImageVersionOS]) -> list[ImageVersionOS]:
        """Ensures that if only one OS is defined, it is marked as primary.

        :param os: List of ImageVersionOS objects to check.

        :return: The list of ImageVersionOS objects with single OS marked primary.
        """
        if len(os) == 1:
            os[0].primary = True
        return os

    @field_validator("dependencyConstraints", mode="after")
    @classmethod
    def check_duplicate_dependency_constraints(
        cls, dependency_constraints: list[DependencyConstraintField], info: ValidationInfo
    ) -> list[DependencyConstraintField]:
        """Ensures that there are no duplicate dependency constraints in the matrix.

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
                    error_message = "Duplicate dependency constraints found in image matrix:\n"
                error_message += f" - {dc.dependency}\n"
            seen_dependencies.add(dc.dependency)
        if error_message:
            raise ValueError(error_message.strip())
        return dependency_constraints

    @field_validator("dependencies", mode="after")
    @classmethod
    def check_duplicate_dependencies(cls, dependencies: list[DependencyVersionsField]) -> list[DependencyVersionsField]:
        """Ensures that the dependencies list is unique and errors on duplicates.

        :param dependencies: List of dependencies to deduplicate.

        :return: A list of unique dependencies.

        :raises ValueError: If duplicate dependencies are found.
        """
        error_message = ""
        seen_dependencies = set()
        for d in dependencies:
            if d.dependency in seen_dependencies:
                if not error_message:
                    error_message = "Duplicate dependency definition found in image matrix:\n"
                error_message += f" - {d.dependency}\n"
            seen_dependencies.add(d.dependency)

        if error_message:
            raise ValueError(error_message.strip())

        return dependencies

    @model_validator(mode="after")
    def validate_os_settings(self) -> "ImageMatrix":
        """Validate OS settings after all fields are available."""
        # Check if OS list is empty
        if not self.os:
            log.warning(
                f"No OSes defined for image matrix with name pattern '{self.namePattern}'. At least one OS "
                "should be defined for complete tagging and labeling of images."
            )
            return self

        # Check primary OS count
        primary_os_count = sum(1 for o in self.os if o.primary)
        if primary_os_count > 1:
            raise ValueError(
                f"Only one OS can be marked as primary for image matrix with name pattern "
                f"'{self.namePattern}'. Found {primary_os_count} OSes marked primary."
            )
        elif primary_os_count == 0:
            log.warning(
                f"No OS marked as primary for image matrix with name pattern '{self.namePattern}'. "
                "At least one OS should be marked as primary for complete tagging and labeling of images."
            )

        return self

    @model_validator(mode="after")
    def extra_registries_or_override_registries(self) -> "ImageMatrix":
        """Ensures that only one of extraRegistries or overrideRegistries is defined.

        :raises ValueError: If both extraRegistries and overrideRegistries are defined.
        """
        if self.extraRegistries and self.overrideRegistries:
            raise ValueError(
                f"Only one of 'extraRegistries' or 'overrideRegistries' can be defined for "
                f"image matrix '{self.namePattern}'."
            )
        return self

    @model_validator(mode="after")
    def resolve_parentage(self) -> "ImageMatrix":
        """Sets the parent for all OSes in this image matrix."""
        for version_os in self.os:
            version_os.parent = self
        return self

    @model_validator(mode="after")
    def check_no_conflicting_dependency_definitions(self) -> "ImageMatrix":
        """Ensures that no dependencies are defined in both dependencies and dependencyConstraints.

        :raises ValueError: If a dependency is defined in both dependencies and dependencyConstraints.
        """
        dependency_names = {d.dependency for d in self.dependencies}
        conflicting_dependencies = [
            dc.dependency for dc in self.dependencyConstraints if dc.dependency in dependency_names
        ]
        if conflicting_dependencies:
            raise ValueError(
                f"The following dependencies are defined in both 'dependencies' and 'dependencyConstraints' for "
                f"image matrix with name pattern '{self.namePattern}': {', '.join(conflicting_dependencies)}"
            )
        return self

    @property
    def resolved_dependencies(self) -> list[DependencyVersions]:
        """Returns the list of resolved dependencies for this image version.

        :return: A list of DependencyVersions objects.
        """
        resolved = deepcopy(self.dependencies)
        for dc in self.dependencyConstraints:
            resolved.append(dc.resolve_versions())

        return resolved

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
    def _flatten_dependencies(dependencies: list[DependencyVersionsField]) -> list[list[DependencyVersionsField]]:
        """Flattens the dependency versions into a list of single-version DependencyVersionsField objects.

        :param dependencies: List of DependencyVersionsField objects.

        :return: A flattened list of lists of DependencyVersionsField objects.
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
    def _flatten_values(values: dict[str, Any]) -> list[list[dict[str, Any]]]:
        """Flattens the values into a list of lists of single-value dictionaries.

        :param values: Dictionary of values.

        :return: A flattened list of lists of dictionaries.
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

        :return: A list of dictionaries, each containing 'dependencies' (list) and 'values' (dict) keys.
        """
        flattened_dependencies = ImageMatrix._flatten_dependencies(dependencies)
        flattened_values = ImageMatrix._flatten_values(values)

        products = itertools.product(*flattened_dependencies, *flattened_values)

        grouped_products = []
        for product in products:
            grouped: dict[str, list | dict] = {"dependencies": [], "values": {}}
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

        products = self._cartesian_product(self.resolved_dependencies, self.values)
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
                isMatrixVersion=True,
            )
            image_versions.append(image_version)

        return image_versions
