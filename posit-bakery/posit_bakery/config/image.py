import logging
from copy import deepcopy
from pathlib import Path
from typing import Annotated, Self, Union

import jinja2
from pydantic import BaseModel, Field, model_validator, computed_field, field_validator, HttpUrl
from pydantic_core.core_schema import ValidationInfo

from posit_bakery.config.registry import Registry
from posit_bakery.config.shared import BakeryPathMixin, BakeryYAMLModel, ExtensionField, TagDisplayNameField
from posit_bakery.config.tag import TagPattern, default_tag_patterns
from posit_bakery.config.templating.filters import jinja2_env
from posit_bakery.config.tools import ToolField, default_tool_options, ToolOptions

log = logging.getLogger(__name__)


class ImageVersionOS(BakeryYAMLModel):
    """Model representing a supported operating system for an image version."""

    parent: Annotated[
        Union[BaseModel, None] | None, Field(exclude=True, default=None, description="Parent ImageVersion object.")
    ]
    name: Annotated[
        str,
        Field(
            description="The operating system human readable name and version string.",
            examples=["Ubuntu 22.04", "Debian 12"],
        ),
    ]
    primary: Annotated[
        bool, Field(default=False, description="Flag to indicate if this is the primary OS for the image.")
    ]
    extension: Annotated[
        ExtensionField,
        Field(
            description="File extension used in the Containerfile filename in the pattern "
            "Containerfile.<os>.<variant> for this OS. Set to an empty string if no extension is needed.",
            examples=["ubuntu2204", "debian12"],
        ),
    ]
    tagDisplayName: Annotated[
        TagDisplayNameField,
        Field(
            description="The name used in image tags for this OS. This is used to create the tag "
            "in the format <image>:<version>-<os>-<variant>.",
            examples=["ubuntu-22.04", "debian-12"],
        ),
    ]

    def __hash__(self):
        """Unique hash for an ImageVersionOS object."""
        return hash((self.name, self.extension, self.tagDisplayName))

    def __eq__(self, other):
        """Equality check for ImageVersionOS based on name.

        :param other: The other object to compare against.
        """
        if isinstance(other, ImageVersionOS):
            return hash(self) == hash(other)
        return False


class ImageVersion(BakeryPathMixin, BakeryYAMLModel):
    """Model representing a version of an image."""

    parent: Annotated[
        Union[BakeryYAMLModel, None], Field(exclude=True, default=None, description="Parent Image object.")
    ]
    name: Annotated[str, Field(description="The full image version.")]
    subpath: Annotated[
        str,
        Field(
            default_factory=lambda data: data.get("name", "").replace(" ", "-").lower(),
            min_length=1,
            description="Subpath under the image to use for the image version.",
        ),
    ]
    extraRegistries: Annotated[
        list[Registry],
        Field(
            default_factory=list,
            description="List of additional registries to use for this image version with registries defined "
            "globally or for the image.",
        ),
    ]
    overrideRegistries: Annotated[
        list[Registry],
        Field(
            default_factory=list,
            description="List of registries to use in place of registries defined globally or for the image.",
        ),
    ]
    latest: Annotated[
        bool, Field(default=False, description="Flag to indicate if this is the latest version of the image.")
    ]
    os: Annotated[
        list[ImageVersionOS],
        Field(
            default_factory=list,
            validate_default=True,
            description="List of supported ImageVersionOS objects for this image version.",
        ),
    ]

    @field_validator("extraRegistries", "overrideRegistries", mode="after")
    @classmethod
    def deduplicate_registries(cls, registries: list[Registry], info: ValidationInfo) -> list[Registry]:
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
        return list(unique_registries)

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

        return list(unique_oses)

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
            if info.data.get("name"):
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

    @model_validator(mode="after")
    def extra_registries_or_override_registries(self) -> Self:
        """Ensures that only one of extraRegistries or overrideRegistries is defined.

        :raises ValueError: If both extraRegistries and overrideRegistries are defined.
        """
        if self.extraRegistries and self.overrideRegistries:
            raise ValueError(
                f"Only one of 'extraRegistries' or 'overrideRegistries' can be defined for image version '{self.name}'."
            )
        return self

    @model_validator(mode="after")
    def resolve_parentage(self) -> Self:
        """Sets the parent for all OSes in this image version."""
        for version_os in self.os:
            version_os.parent = self
        return self

    @property
    def path(self) -> Path | None:
        """Returns the path to the image version directory.

        :raises ValueError: If the parent image does not have a valid path.
        """
        if self.parent is None or self.parent.path is None:
            raise ValueError("Parent image must resolve a valid path.")
        return Path(self.parent.path) / self.subpath

    @property
    def all_registries(self) -> list[Registry]:
        """Returns the merged registries for this image version.

        :return: A list of registries that includes the overrideRegistiries or the version's extraRegistries and any
            registries from the parent image.
        """
        # If overrideRegistries are set, return those directly.
        if self.overrideRegistries:
            return deepcopy(self.overrideRegistries)

        # Otherwise, merge the registries from the image version and its parent.
        all_registries = deepcopy(self.extraRegistries)
        if self.parent is not None and isinstance(self.parent, Image):
            for registry in self.parent.all_registries:
                if registry not in all_registries:
                    all_registries.append(registry)

        return all_registries


class ImageVariant(BakeryYAMLModel):
    """Model representing a variant of an image."""

    parent: Annotated[
        Union[BakeryYAMLModel, None] | None, Field(exclude=True, default=None, description="Parent Image object.")
    ]
    name: Annotated[str, Field(description="The full human-readable display name of the image variant.")]
    primary: Annotated[
        bool, Field(default=False, description="Flag to indicate if this is the primary variant of the image.")
    ]
    extension: Annotated[
        ExtensionField,
        Field(
            description="File extension used in the Containerfile filename in the pattern Containerfile.<os>.<variant> "
            "for this variant. Set to an empty string if no extension is needed.",
            examples=["std", "min"],
        ),
    ]
    tagDisplayName: Annotated[
        TagDisplayNameField,
        Field(
            description="The name used in image tags for this variant. This is used to create the tag "
            "in the format <image>:<version>-<os>-<variant>.",
            examples=["std", "min"],
        ),
    ]
    tagPatterns: Annotated[
        list[TagPattern], Field(default_factory=list, description="List of tag patterns for this variant.")
    ]
    options: Annotated[
        list[ToolField],
        Field(default_factory=default_tool_options, description="List of tool options for this variant."),
    ]

    def __hash__(self):
        """Unique hash for an ImageVariant object."""
        return hash((self.name, self.extension, self.tagDisplayName))

    def get_tool_option(self, tool: str, merge_with_parent: bool = True) -> ToolOptions | None:
        """Returns tool options for this image variant.

        By default, the tool option for the variant will be merged with the parent image's tool options if they exist.
        Tool options set to non-defaults in the variant will take precedence over those in the parent.

        :param tool: The name of the tool to get options for.

        :return: The ToolOptions object for the specified tool, or None if not found.
        """
        option = None
        parent_option = None

        for o in self.options:
            if o.tool == tool:
                option = o

        if self.parent is not None and merge_with_parent:
            # Check parent image for tool options first
            parent_option = self.parent.get_tool_option(tool)
            if parent_option is not None and option is None:
                # If the parent has options, use them if the variant does not have its own
                return parent_option

        if option and parent_option:
            # Merge the options if both are found
            return option.merge(parent_option)

        return option


def default_image_variants() -> list[ImageVariant]:
    """Return the default image variants for the bakery configuration.

    :return: A list of default image variants.
    """
    return [
        ImageVariant(name="Standard", extension="std", tagDisplayName="std", primary=True),
        ImageVariant(name="Minimal", extension="min", tagDisplayName="min"),
    ]


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
        list[Registry],
        Field(
            default_factory=list,
            validate_default=True,
            description="List of additional registries to use for this image in addition to global registries.",
        ),
    ]
    overrideRegistries: Annotated[
        list[Registry],
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
    variants: Annotated[
        list[ImageVariant],
        Field(
            default_factory=default_image_variants,
            validate_default=True,
            description="List of image variants.",
        ),
    ]
    versions: Annotated[
        list[ImageVersion],
        Field(default_factory=list, validate_default=True, description="List of image versions for this image."),
    ]
    options: Annotated[list[ToolField], Field(default_factory=list, description="List of tool options for this image.")]

    @field_validator("extraRegistries", "overrideRegistries", mode="after")
    @classmethod
    def deduplicate_registries(cls, registries: list[Registry], info: ValidationInfo) -> list[Registry]:
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
        return list(unique_registries)

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

    @field_validator("versions", mode="after")
    @classmethod
    def check_versions_not_empty(cls, versions: list[ImageVersion], info: ValidationInfo) -> list[ImageVersion]:
        """Ensures that the versions list is not empty.

        :param versions: List of ImageVersion objects to check.
        :param info: ValidationInfo containing the data being validated.

        :return: The unmodified list of ImageVersion objects.
        """
        if info.data.get("name") and not versions:
            log.warning(
                f"No versions found in image '{info.data['name']}'. At least one version is required for most commands."
            )
        return versions

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

    @model_validator(mode="after")
    def resolve_parentage(self) -> Self:
        """Sets the parent for all variants and versions in this image."""
        for variant in self.variants:
            variant.parent = self
        for version in self.versions:
            version.parent = self
        return self

    @computed_field
    @property
    def path(self) -> Path | None:
        """Returns the path to the image directory."""
        if self.parent is None or self.parent.path is None:
            raise ValueError("Parent BakeryConfig must resolve a valid path.")
        return Path(self.parent.path) / self.subpath

    @computed_field
    @property
    def template_path(self) -> Path:
        """Returns the path to the image template directory."""
        if self.path is None:
            raise ValueError("Image path must be valid to find template path.")
        return self.path / "template"

    @property
    def all_registries(self) -> list[Registry]:
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

    def generate_version_template_values(
        self,
        version: str,
        variant: str | None = None,
        version_path: str | Path | None = None,
        extra_values: list[str] | None = None,
    ) -> dict[str, str]:
        """Generates the template values for rendering.

        :param version: The version's string representation (name).
        :param variant: The variant's string representation (name).
        :param version_path: The subpath to the version directory, if different from the default.
        :param extra_values: Additional key-value pairs to include in the template values.

        :return: A dictionary of values to use for rendering version templates.
        """
        values = {
            "Image": {
                "Name": self.name,
                "DisplayName": self.displayName,
                "Version": version,
                "Variant": variant or "",
            },
            "VersionPath": str(version_path or (self.path / version).relative_to(self.parent.path)),
            "ImagePath": str(self.path.relative_to(self.parent.path)),
            "BasePath": ".",
        }
        if extra_values:
            for v in extra_values:
                key, value = v.split("=", 1)
                values[key] = value

        return values

    @staticmethod
    def create_version_files(
        version: ImageVersion,
        variants: list[ImageVariant] | None = None,
        extra_values: list[str] | None = None,
    ):
        """Render a new image version from the template.

        :param version: The ImageVersion object to render.
        :param variants: Optional list of ImageVariant objects to render Containerfiles for each variant.
        :param extra_values: Optional list of additional key-value pairs to include in the template values
        """
        # Check that template path exists
        if not version.parent.template_path.is_dir():
            raise ValueError(f"Image template path does not exist: {version.parent.template_path}")

        # Create new version directory
        if not version.path.is_dir():
            log.debug(f"Creating new image version directory [bold]{version.path}")
            version.path.mkdir()

        env = jinja2_env(
            loader=jinja2.FileSystemLoader(version.parent.template_path),
            autoescape=True,
            undefined=jinja2.StrictUndefined,
            keep_trailing_newline=True,
        )

        # Render templates to version directory
        for tpl_rel_path in env.list_templates():
            tpl = env.get_template(tpl_rel_path)

            # Enable trim_blocks for Containerfile templates
            render_kwargs = {}
            if tpl_rel_path.startswith("Containerfile"):
                render_kwargs["trim_blocks"] = True

            # If variants are specified, render Containerfile for each variant
            if tpl_rel_path.startswith("Containerfile") and variants:
                containerfile_base_name = tpl_rel_path.removesuffix(".jinja2")
                for variant in variants:
                    template_values = version.parent.generate_version_template_values(
                        version.name, variant.name, version.path, extra_values
                    )
                    containerfile: Path = version.path / f"{containerfile_base_name}.{variant.extension}"
                    rendered = tpl.render(**template_values, **render_kwargs)
                    with open(containerfile, "w") as f:
                        log.debug(f"Rendering [bold]{containerfile}")
                        f.write(rendered)

            # Render other templates once
            else:
                template_values = version.parent.generate_version_template_values(
                    version, version_path=version.path, extra_values=extra_values
                )
                rendered = tpl.render(**template_values, **render_kwargs)
                rel_path = tpl_rel_path.removesuffix(".jinja2")
                output_file = version.path / rel_path
                output_file.parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, "w") as f:
                    log.debug(f"[bright_black]Rendering [bold]{output_file}")
                    f.write(rendered)

    def create_version_model(
        self,
        version_name: str,
        subpath: str | None = None,
        latest: bool = True,
        update_if_exists: bool = False,
    ) -> ImageVersion:
        """Creates a new image version and adds it to the image.

        :param version_name: The name of the new image version.
        :param subpath: Optional subpath for the new version. If None, defaults to the version name with spaces replaced
            by hyphens and lowercase.
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
                    if v.extraRegistries:
                        registries = deepcopy(v.extraRegistries)
                v.latest = False

            # Setup the arguments for the new version. Leave out fields that are None so they are defaulted.
            args = {"name": version_name, "parent": self}
            if subpath is not None:
                args["subpath"] = subpath
            if os is not None:
                args["os"] = os
            if registries is not None:
                args["registries"] = registries

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

        return image_version
