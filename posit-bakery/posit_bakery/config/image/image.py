import logging
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Annotated, Union, Any, Self

from pydantic import Field, HttpUrl, field_validator, model_validator, field_serializer
from pydantic_core.core_schema import ValidationInfo

from posit_bakery.config.dependencies import DependencyConstraintField, DependencyVersions, DependencyConstraint
from posit_bakery.config.registry import BaseRegistry, Registry
from posit_bakery.config.shared import BakeryPathMixin, BakeryYAMLModel
from posit_bakery.config.tag import default_tag_patterns, TagPattern
from posit_bakery.config.tools import ToolField, ToolOptions
from .dev_version import DevelopmentVersionField
from .matrix import ImageMatrix
from .variant import ImageVariant
from .version import ImageVersion

log = logging.getLogger(__name__)


class Image(BakeryPathMixin, BakeryYAMLModel):
    """Model representing an image in the bakery configuration."""

    parent: Annotated[
        Union[BakeryYAMLModel, None] | None,
        Field(exclude=True, default=None, description="Parent BakeryDocumentConfig object."),
    ]
    name: Annotated[str, Field(description="The name of the image, used for tagging and labeling.")]
    displayName: Annotated[
        str,
        Field(
            default_factory=lambda data: data.get("name", "").replace("-", " ").title(),
            description="Human-readable display name of the image.",
        ),
    ]
    description: Annotated[str | None, Field(default=None, description="Description of the image. Used for labeling.")]
    documentationUrl: Annotated[
        HttpUrl | None, Field(default=None, description="URL to the image documentation. Used for labeling")
    ]
    subpath: Annotated[
        str,
        Field(
            default_factory=lambda data: data.get("name", "").replace(" ", "-").lower(),
            min_length=1,
            description="Subpath to use for the image.",
        ),
    ]
    extraRegistries: Annotated[
        list[Registry | BaseRegistry],
        Field(
            default_factory=list,
            validate_default=True,
            description="List of additional registries to use for this image in addition to global registries.",
        ),
    ]
    overrideRegistries: Annotated[
        list[Registry | BaseRegistry],
        Field(
            default_factory=list,
            validate_default=True,
            description="List of registries to use in place of registries defined globally or for the image.",
        ),
    ]
    tagPatterns: Annotated[
        list[TagPattern],
        Field(
            default_factory=default_tag_patterns,
            validate_default=True,
            description="List of tag patterns for this image.",
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
    variants: Annotated[
        list[ImageVariant],
        Field(
            default_factory=list,
            validate_default=True,
            description="List of image variants.",
        ),
    ]
    versions: Annotated[
        list[ImageVersion],
        Field(default_factory=list, validate_default=True, description="List of image versions for this image."),
    ]
    devVersions: Annotated[
        list[DevelopmentVersionField],
        Field(default_factory=list, description="List of development versions for this image."),
    ]
    matrix: Annotated[
        ImageMatrix | None,
        Field(
            default=None,
            validate_default=True,
            description="Matrix configuration for generating image versions.",
        ),
    ]
    options: Annotated[list[ToolField], Field(default_factory=list, description="List of tool options for this image.")]

    @field_validator("documentationUrl", mode="before")
    @classmethod
    def default_https_url_scheme(cls, value: Any) -> Any:
        """Prepend 'https://' to the URL if it does not already start with it.

        :param value: The URL to validate and possibly modify.
        """
        if isinstance(value, str):
            if not value.startswith("https://") and not value.startswith("http://"):
                value = f"https://{value}"
        return value

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
            if info.data.get("name") and registries.count(unique_registry) > 1:
                log.warning(
                    f"Duplicate registry defined in config for image '{info.data['name']}': {unique_registry.base_url}"
                )
        return sorted(list(unique_registries), key=lambda r: r.base_url)

    @model_validator(mode="after")
    def extra_registries_or_override_registries(self) -> Self:
        """Ensures that only one of extraRegistries or overrideRegistries is defined.

        :raises ValueError: If both extraRegistries and overrideRegistries are defined.
        """
        if self.extraRegistries and self.overrideRegistries:
            raise ValueError(
                f"Only one of 'extraRegistries' or 'overrideRegistries' can be defined for image '{self.name}'."
            )
        return self

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

    @field_validator("versions", mode="after")
    @classmethod
    def check_version_duplicates(cls, versions: list[ImageVersion], info: ValidationInfo) -> list[ImageVersion]:
        """Ensures that there are no duplicate version names in the image.

        :param versions: List of ImageVersion objects to check for duplicates.
        :param info: ValidationInfo containing the data being validated.

        :return: The unmodified list of ImageVersion objects if no duplicates are found.

        :raises ValueError: If duplicate version names are found.
        """
        error_message = ""
        seen_names = set()
        for version in versions:
            if version.name in seen_names:
                if not error_message:
                    error_message = f"Duplicate versions found in image '{info.data['name']}':\n"
                error_message += f" - {version.name}\n"
            seen_names.add(version.name)
        if error_message:
            raise ValueError(error_message.strip())
        return versions

    @field_validator("variants", mode="after")
    @classmethod
    def check_variant_duplicates(cls, variants: list[ImageVariant], info: ValidationInfo) -> list[ImageVariant]:
        """Ensures that there are no duplicate variant names in the image.

        :param variants: List of ImageVariant objects to check for duplicates.
        :param info: ValidationInfo containing the data being validated.

        :return: The unmodified list of ImageVariant objects if no duplicates are found.

        :raises ValueError: If duplicate variant names are found.
        """
        error_message = ""
        seen_names = set()
        for variant in variants:
            if variant.name in seen_names:
                if not error_message:
                    error_message = f"Duplicate variants found in image '{info.data['name']}':\n"
                error_message += f" - {variant.name}\n"
            seen_names.add(variant.name)
        if error_message:
            raise ValueError(error_message.strip())
        return variants

    @model_validator(mode="before")
    @classmethod
    def check_matrix_or_versions(cls, data) -> dict:
        """Ensures that only one of matrix or versions and devVersions are defined for the image.

        :param data: The data being validated.

        :return: The unmodified data dictionary.

        :raises ValueError: If neither matrix nor versions are defined.
        """
        if data.get("matrix") and (data.get("versions") or data.get("devVersions")):
            raise ValueError(
                f"Only one of 'matrix' or 'versions'/'devVersions' can be defined for image '{data.get('name')}'."
            )
        return data

    @model_validator(mode="after")
    def resolve_parentage(self) -> Self:
        """Sets the parent for all variants and versions in this image."""
        for variant in self.variants:
            variant.parent = self
        for version in self.versions:
            version.parent = self
        for dev_version in self.devVersions:
            dev_version.parent = self
        if self.matrix is not None:
            self.matrix.parent = self
        return self

    @model_validator(mode="after")
    def check_not_empty(self) -> Self:
        """Ensures one version or matrix is defined.

        :return: The unmodified Image object.
        """
        if self.name and not self.versions and not self.devVersions and not self.matrix:
            log.warning(
                f"No versions, devVersions, or matrix found in image '{self.name}'. At least one is required for most "
                f"commands."
            )
        return self

    @model_validator(mode="after")
    def check_dependency_constraints_with_matrix(self) -> Self:
        """Checks if dependencyConstraints and matrix are both defined.

        Warns if dependencyConstraints will be ineffectual as they must be defined at matrix-level.
        """
        if self.matrix is not None and self.dependencyConstraints:
            log.warning(
                f"Image '{self.name}' defines both 'dependencyConstraints' and a 'matrix'. "
                f"Image-level 'dependencyConstraints' will be ignored; define them at the matrix-level instead."
            )

        return self

    @field_serializer("documentationUrl")
    def serialize_documentation_url(self, value: HttpUrl | None) -> str | None:
        """Serializes the documentation URL to a string."""
        if value is None:
            return None
        return str(value)

    @property
    def path(self) -> Path | None:
        """Returns the path to the image directory."""
        if self.parent is None or self.parent.path is None:
            raise ValueError("Parent BakeryConfig must resolve a valid path.")
        return Path(self.parent.path) / Path(self.subpath)

    @property
    def template_path(self) -> Path:
        """Returns the path to the image template directory."""
        if self.path is None:
            raise ValueError("Image path must be valid to find template path.")
        return self.path / "template"

    @property
    def all_registries(self) -> list[Registry | BaseRegistry]:
        """Returns the merged registries for this image."""
        # If overrideRegistries are set, return those directly.
        if self.overrideRegistries:
            return deepcopy(self.overrideRegistries)

        # Otherwise, merge the registries from the image and its parent.
        all_registries = deepcopy(self.extraRegistries)
        if self.parent is not None:
            for registry in self.parent.registries:
                if registry not in all_registries:
                    all_registries.append(registry)

        return all_registries

    def resolve_dependency_versions(self) -> list[DependencyVersions]:
        """Resolves the dependency versions for this image.

        :return: A list of DependencyVersions objects with resolved versions.
        """
        return [dc.resolve_versions() for dc in self.dependencyConstraints]

    def get_tool_option(self, tool: str) -> ToolOptions | None:
        """Returns the Goss options for this image variant.

        :param tool: The name of the tool to get options for.

        :return: The ToolOptions object for the specified tool, or None if not found.
        """
        for option in self.options:
            if option.tool == tool:
                return option

        return None

    def get_variant(self, name: str) -> ImageVariant | None:
        """Returns an image variant by name, or None if not found.

        :param name: The name property of the image variant to find.

        :return: The ImageVariant object if found, otherwise None.
        """
        for variant in self.variants:
            if variant.name == name:
                return variant

        return None

    def get_version(self, name: str) -> ImageVersion | None:
        """Returns an image version by name, or None if not found.

        :param name: The name property of the image version to find.

        :return: The ImageVersion object if found, otherwise None.
        """
        for version in self.versions:
            if version.name == name:
                return version

        return None

    def create_version(
        self,
        version_name: str,
        subpath: str | None = None,
        values: dict[str, str] | None = None,
        latest: bool = True,
        update_if_exists: bool = False,
    ) -> ImageVersion:
        """Creates a new image version and adds it to the image.

        :param version_name: The name of the new image version.
        :param subpath: Optional subpath for the new version. If None, defaults to the version name with spaces replaced
            by hyphens and lowercase.
        :param values: Optional dictionary of additional key-value pairs to include in the template values.
        :param latest: If True, sets this version as the latest version of the image. Unsets latest on all other image
            versions.
        :param update_if_exists: If True, updates the existing version if it already exists, otherwise raises an error
            if the version exists.

        :return: The created or updated ImageVersion object.
        """
        # Check if the version already exists
        image_version = self.get_version(version_name)
        # If it exists and update_if_exists is False, raise an error.
        if image_version is not None and not update_if_exists:
            raise ValueError(f"Version '{version_name}' already exists in image '{self.name}'.")

        # Logic for creating a new version.
        if image_version is None:
            # Copy the latest OS and registries if they exist and unset latest on all other versions.
            os = None
            registries = None
            for v in self.versions:
                if v.latest:
                    if v.os:
                        os = deepcopy(v.os)
                v.latest = False

            # Setup the arguments for the new version. Leave out fields that are None so they are defaulted.
            dependency_versions = self.resolve_dependency_versions()
            log_message = "Resolved dependency versions:"
            for dep in dependency_versions:
                log_message += f"\n  - {dep.dependency}: {', '.join(dep.versions)}"
            log.debug(log_message)

            args = {
                "name": version_name,
                "parent": self,
                "dependencies": dependency_versions,
            }
            if subpath is not None:
                args["subpath"] = subpath
            if values is not None:
                args["values"] = values
            if os is not None:
                args["os"] = os
            if registries is not None:
                args["registries"] = registries
            if latest:
                args["latest"] = True

            image_version = ImageVersion(**args)
            self.versions.append(image_version)

        # Logic for updating an existing version.
        else:
            if latest:
                # Unset latest on all other versions and set this one to latest.
                for v in self.versions:
                    v.latest = False
                image_version.latest = True
            if subpath:
                image_version.subpath = subpath
            if values:
                image_version.values = values

        return image_version

    def create_matrix(
        self,
        name_pattern: str | None = None,
        subpath: str | None = None,
        dependency_constraints: list[DependencyConstraint] | None = None,
        dependencies: list[DependencyVersions] | None = None,
        values: dict[str, str] | None = None,
        update_if_exists: bool = False,
    ) -> ImageMatrix:
        """Creates a new image version and adds it to the image.

        :param name_pattern: The name pattern for the new image version. If None, defaults to the version name with
            spaces replaced by hyphens and lowercase.
        :param subpath: Optional subpath for the new version. If None, defaults to the version name with spaces replaced
            by hyphens and lowercase.
        :param dependency_constraints: Optional list of DependencyConstraint objects to use for resolving
            dependencies for the new version.
        :param dependencies: Optional list of DependencyVersions objects to use for the new version.
        :param values: Optional dictionary of additional key-value pairs to include in the template values.
        :param update_if_exists: If True, updates the existing version if it already exists, otherwise raises an error
            if the version exists.

        :return: The created or updated ImageVersion object.
        """
        # If versions or devVersions are defined, raise an error.
        if self.versions or self.devVersions:
            raise ValueError(
                f"Cannot create matrix version for image '{self.name}' because versions or devVersions are already "
                f"defined."
            )
        # If matrix exists and update_if_exists is False, raise an error.
        if self.matrix is not None and not update_if_exists:
            raise ValueError(f"Matrix already defined for image '{self.name}'.")

        # Logic for creating a new version.
        if self.matrix is None:
            args = {
                "parent": self,
                "dependencyConstraints": dependency_constraints or [],
                "dependencies": dependencies or [],
                "values": values or {},
            }
            if name_pattern is not None:
                args["namePattern"] = name_pattern
            if subpath is not None:
                args["subpath"] = subpath

            self.matrix = ImageMatrix(**args)

        # Logic for updating an existing version.
        else:
            if name_pattern is not None:
                self.matrix.namePattern = name_pattern
            if subpath is not None:
                self.matrix.subpath = subpath
            if dependency_constraints is not None:
                self.matrix.dependencyConstraints = dependency_constraints
            if dependencies is not None:
                self.matrix.dependencies = dependencies
            if values is not None:
                self.matrix.values = values

        return self.matrix

    def patch_version(
        self,
        old_version_name: str,
        new_version_name: str,
        values: dict[str, str] = None,
        clean: bool = True,
    ) -> ImageVersion:
        """Patches an existing image version with a new version name.

        :param old_version_name: The existing version name to be patched.
        :param new_version_name: The new version name to replace the old version with.
        :param values: Optional dictionary of additional key-value pairs to include or update in the template values.
        :param clean: If True, removes all existing version files before rendering the new version files

        :return: The patched ImageVersion object.
        """
        # Check if the old version exists
        image_version = self.get_version(old_version_name)
        if image_version is None:
            raise ValueError(
                f"Version '{old_version_name}' does not exist for image '{self.name}'. Use the `bakery create version` "
                f"command instead."
            )

        # Check if the new version already exists
        if self.get_version(new_version_name) is not None:
            raise ValueError(f"Version '{new_version_name}' already exists in image '{self.name}'.")

        original_version_data = image_version.model_dump(exclude_defaults=True, exclude_none=True, exclude_unset=True)
        original_path = image_version.path

        # Patch the version name
        original_version_data["name"] = new_version_name

        # Patch the version values if provided
        if values is not None:
            original_version_data.setdefault("values", {}).update(values)

        # Recreate the ImageVersion object to ensure all properties are updated correctly.
        patched_image_version = ImageVersion(**original_version_data)
        patched_image_version.parent = self
        self.versions.append(patched_image_version)

        # Pop the old version from the versions list for this image.
        self.versions.remove(image_version)

        # Fix or remove paths based on the clean and subpath settings.
        if patched_image_version.path != image_version.path:
            if clean:
                log.debug(f"Removing existing version files for '{old_version_name}' at [bold]{original_path}")
                shutil.rmtree(image_version.path)
            else:
                shutil.move(image_version.path, patched_image_version.path)
        elif clean:
            log.debug(f"Removing existing version files for '{old_version_name}' at [bold]{image_version.path}")
            shutil.rmtree(image_version.path)

        # Render the version files.
        patched_image_version.render_files(variants=self.variants)

        return patched_image_version

    def load_dev_versions(self):
        """Load the development versions for this image."""
        for dev_version in self.devVersions:
            image_version = dev_version.as_image_version()
            log_message = f"Loaded {self.name} development version from {repr(dev_version)}:\n"
            log_message += f"  - Version: {image_version.name}\n"
            for dep in image_version.dependencies:
                log_message += f"  - Dependency: {dep.dependency} {', '.join(dep.versions)}\n"
            log.info(log_message.strip())
            self.versions.append(image_version)

    def render_ephemeral_version_files(self):
        """Create the files for all ephemeral image versions."""
        for version in self.versions:
            if version.ephemeral:
                log.debug(f"Creating ephemeral image version directory [bold]{version.path}")
                version.render_files(variants=self.variants)

    def remove_ephemeral_version_files(self):
        """Remove the files for all ephemeral image versions."""
        for version in self.versions:
            if version.ephemeral and version.path.is_dir():
                log.debug(f"Removing ephemeral image version directory [bold]{version.path}")
                shutil.rmtree(version.path)
