import logging
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Annotated, Union, Any, Self

import jinja2
from pydantic import Field, HttpUrl, field_validator, model_validator, field_serializer
from pydantic_core.core_schema import ValidationInfo

from .dev_version import DevelopmentVersionField
from .variant import ImageVariant
from .version import ImageVersion
from posit_bakery.config.dependencies import DependencyConstraintField
from posit_bakery.config.registry import Registry
from posit_bakery.config.shared import BakeryPathMixin, BakeryYAMLModel
from posit_bakery.config.tag import default_tag_patterns, TagPattern
from posit_bakery.config.templating import jinja2_env
from posit_bakery.config.tools import ToolField, ToolOptions

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
        for dev_version in self.devVersions:
            dev_version.parent = self
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
        version: "ImageVersion",
        variant: Union["ImageVariant", None] = None,
        version_os: Union["ImageVersionOS", None] = None,
        version_path: str | Path | None = None,
        extra_values: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Generates the template values for rendering.

        :param version: The ImageVersion object.
        :param variant: The ImageVariant object.
        :param version_os: The ImageVersionOS object, if applicable.
        :param version_path: The subpath to the version directory, if different from the default.
        :param extra_values: Additional key-value pairs to include in the template values.

        :return: A dictionary of values to use for rendering version templates.
        """
        values = {
            "Image": {
                "Name": self.name,
                "DisplayName": self.displayName,
                "Version": version.name,
            },
            "Path": {
                "Base": ".",
                "Image": str(self.path.relative_to(self.parent.path)),
                "Version": str((Path(version_path) or self.path / version).relative_to(self.parent.path)),
            },
        }
        if variant is not None:
            values["Image"]["Variant"] = variant.name
        if version_os:
            values["Image"]["OS"] = {
                "Name": version_os.buildOS.name,
                "Family": version_os.buildOS.family,
                "Version": version_os.buildOS.version,
                "Codename": version_os.buildOS.codename,
            }
            if version_os.artifactDownloadURL is not None:
                values["Image"]["DownloadURL"] = version_os.downloadURL
        if extra_values:
            values.update(extra_values)

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
            version.path.mkdir(parents=True)

        env = jinja2_env(
            loader=jinja2.ChoiceLoader(
                [
                    jinja2.FileSystemLoader(version.parent.template_path),
                    jinja2.PackageLoader("posit_bakery.config.templates", "templating"),
                ]
            ),
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

                # Attempt to match the OS from the Containerfile name
                os_ext = containerfile_base_name.split(".")[-1]
                containerfile_os = None
                for _os in version.os:
                    if _os.extension == os_ext:
                        containerfile_os = _os
                        break

                for variant in variants:
                    template_values = version.parent.generate_version_template_values(
                        version, variant, containerfile_os, version.path, extra_values
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
                v.latest = False

            # Setup the arguments for the new version. Leave out fields that are None so they are defaulted.
            args = {"name": version_name, "parent": self}
            if subpath is not None:
                args["subpath"] = subpath
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

        return image_version

    def load_dev_versions(self):
        """Load the development versions for this image."""
        for dev_version in self.devVersions:
            image_version = dev_version.as_image_version()
            self.versions.append(image_version)

    def create_ephemeral_version_files(self, extra_values: dict[str, str] | None = None):
        """Create the files for all ephemeral image versions."""
        # TODO: Replace the extra_values parameter with Ben's dependency constraints resolution.
        for version in self.versions:
            if version.ephemeral:
                log.debug(f"Creating ephemeral image version directory [bold]{version.path}")
                self.create_version_files(version, self.variants, extra_values=extra_values)

    def remove_ephemeral_version_files(self):
        """Remove the files for all ephemeral image versions."""
        for version in self.versions:
            if version.ephemeral and version.path.is_dir():
                log.debug(f"Removing ephemeral image version directory [bold]{version.path}")
                shutil.rmtree(version.path)
