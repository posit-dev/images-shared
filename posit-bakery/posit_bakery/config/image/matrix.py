import itertools
import logging
import re
from pathlib import Path
from typing import Annotated, Union, Self, Any

import jinja2
from pydantic import Field, field_validator, model_validator
from pydantic_core.core_schema import ValidationInfo

from posit_bakery.config.dependencies import (
    DependencyVersionsField,
    DependencyConstraintField,
    get_dependency_versions_class,
    DependencyVersions,
)
from posit_bakery.config.image.build_os import TargetPlatform, DEFAULT_PLATFORMS
from posit_bakery.config.registry import BaseRegistry, Registry
from posit_bakery.config.shared import BakeryPathMixin, BakeryYAMLModel
from posit_bakery.config.templating import jinja2_env
from .version import ImageVersion
from .version_os import ImageVersionOS
from .. import ImageVariant
from ...error import BakeryFileError, BakeryRenderError, BakeryTemplateError, BakeryRenderErrorGroup

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


class ImageMatrix(BakeryPathMixin, BakeryYAMLModel):
    """Model representing a matrix of a image value combinations to build."""

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
                    "Duplicate registry defined in config for image matrix with name pattern "
                    f"'{info.data['namePattern']}': {unique_registry.base_url}"
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
        if info.data.get("namePattern") and not os:
            log.warning(
                f"No OSes defined for image matrix with name pattern '{info.data['namePattern']}'. At least one OS "
                "should be defined for complete tagging and labeling of images."
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
            if info.data.get("namePattern") and os.count(unique_os) > 1:
                log.warning(
                    "Duplicate OS defined in config for image matrix with name pattern "
                    f"'{info.data['namePattern']}': {unique_os.name}"
                )

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
            if info.data.get("namePattern") and not os[0].primary:
                log.info(
                    "Only one OS, {os[0].name}, defined for image matrix with name pattern "
                    f"{info.data['namePattern']}. Marking it as primary OS."
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
        if info.data.get("namePattern") and primary_os_count > 1:
            raise ValueError(
                f"Only one OS can be marked as primary for image matrix with name pattern "
                f"'{info.data['namePattern']}'. Found {primary_os_count} OSes marked primary."
            )
        elif info.data.get("namePattern") and primary_os_count == 0:
            log.warning(
                f"No OS marked as primary for image matrix with name pattern '{info.data['namePattern']}'. "
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
                    error_message = f"Duplicate dependency constraints found in image matrix:\n"
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
                    error_message = f"Duplicate dependency or dependency constraints found in image matrix:\n"
                error_message += f" - {d.dependency}\n"
            seen_dependencies.add(d.dependency)

        if error_message:
            raise ValueError(error_message.strip())

        return dependencies

    @model_validator(mode="after")
    def extra_registries_or_override_registries(self) -> Self:
        """Ensures that only one of extraRegistries or overrideRegistries is defined.

        :raises ValueError: If both extraRegistries and overrideRegistries are defined.
        """
        if self.extraRegistries and self.overrideRegistries:
            raise ValueError(
                f"Only one of 'extraRegistries' or 'overrideRegistries' can be defined for image matrix with name "
                f"pattern '{self.namePattern}'."
            )
        return self

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

    def generate_template_values(
        self,
        variant: Union["ImageVariant", None] = None,
        version_os: Union["ImageVersionOS", None] = None,
    ) -> dict[str, Any]:
        """Generates the template values for rendering.

        :param variant: The ImageVariant object.
        :param version_os: The ImageVersionOS object, if applicable.

        :return: A dictionary of values to use for rendering version templates.
        """
        values = {
            "Image": {
                "Name": self.parent.name,
                "DisplayName": self.parent.displayName,
            },
            "Path": {
                "Base": ".",
                "Image": str(self.parent.path.relative_to(self.parent.parent.path)),
                "Version": str(Path(self.parent.path / self.subpath).relative_to(self.parent.parent.path)),
            },
        }
        if variant is not None:
            values["Image"]["Variant"] = variant.name
        if version_os is not None:
            values["Image"]["OS"] = {
                "Name": version_os.buildOS.name,
                "Family": version_os.buildOS.family.value,
                "Version": version_os.buildOS.version,
                "Codename": version_os.buildOS.codename,
            }

        return values

    def render_files(self, variants: list[ImageVariant] | None = None, regex_filters: list[str] | None = None):
        """Render matrix file definitions from templates.

        :param variants: Optional list of ImageVariant objects to render Containerfiles for each variant.
        :param regex_filters: Optional list of regex patterns to filter which templates to render.

        :raises BakeryFileError: If the template path does not exist.
        :raises BakeryRenderError: If a template fails to render.
        :raises BakeryRenderErrorGroup: If multiple templates fail to render.
        """
        # Check that template path exists
        if not self.parent.template_path.is_dir():
            raise BakeryFileError(f"Image '{self.parent.name}' template path does not exist", self.parent.template_path)

        # Create new version directory
        if not self.path.is_dir():
            log.debug(f"Creating new image version directory [bold]{self.path}")
            self.path.mkdir(parents=True)

        env = jinja2_env(
            loader=jinja2.ChoiceLoader(
                [
                    jinja2.FileSystemLoader(self.parent.template_path),
                    jinja2.PackageLoader("posit_bakery.config.templating", "macros"),
                ]
            ),
            autoescape=True,
            undefined=jinja2.StrictUndefined,
            keep_trailing_newline=True,
        )

        exceptions = []

        # Render templates to version directory
        # This is using walk instead of list_templates to ensure that the macro files are not rendered into the version.
        for root, dirs, files in self.parent.template_path.walk():
            for file in files:
                tpl_full_path = (Path(root) / file).resolve()
                tpl_rel_path = str(tpl_full_path.relative_to(self.parent.template_path))

                for regex in regex_filters or []:
                    if not re.match(regex, tpl_rel_path):
                        log.debug(f"Skipping template [bright_black]{tpl_rel_path}[/] due to filter [bold]{regex}[/]")
                        continue
                try:
                    tpl = env.get_template(tpl_rel_path)
                except jinja2.TemplateError as e:
                    log.error(f"Failed to load template [bold]{tpl_rel_path}[/] for image '{self.parent.name}'")
                    exceptions.append(
                        BakeryRenderError(
                            cause=e,
                            context=self.parent.parent.path,
                            image=self.parent.name,
                            version="matrix",
                            template=Path(tpl_full_path),
                        )
                    )
                    continue

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
                    for _os in self.os:
                        if _os.extension == os_ext:
                            containerfile_os = _os
                            break

                    for variant in variants:
                        template_values = self.generate_template_values(variant, containerfile_os)
                        containerfile: Path = self.path / f"{containerfile_base_name}.{variant.extension}"
                        try:
                            rendered = tpl.render(**template_values, **render_kwargs)
                        except (jinja2.TemplateError, BakeryTemplateError) as e:
                            log.error(
                                f"Failed to render template [bold]{tpl_rel_path}[/] for image '{self.parent.name}' "
                                f"matrix variant '{variant.name}'"
                            )
                            exceptions.append(
                                BakeryRenderError(
                                    cause=e,
                                    context=self.parent.parent.path,
                                    image=self.parent.name,
                                    version="matrix",
                                    variant=variant.name,
                                    template=Path(tpl_full_path),
                                    destination=Path(containerfile),
                                )
                            )
                            continue
                        with open(containerfile, "w") as f:
                            log.debug(f"[bright_black]Rendering [bold]{containerfile}")
                            f.write(rendered)

                # Render other templates once
                else:
                    rel_path = tpl_rel_path.removesuffix(".jinja2")
                    output_file = self.path / rel_path
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    template_values = self.generate_template_values()
                    try:
                        rendered = tpl.render(**template_values, **render_kwargs)
                    except (jinja2.TemplateError, BakeryTemplateError) as e:
                        log.error(
                            f"Failed to render template [bold]{tpl_rel_path}[/] for image '{self.parent.name}' matrix"
                        )
                        exceptions.append(
                            BakeryRenderError(
                                cause=e,
                                context=self.parent.parent.path,
                                image=self.parent.name,
                                version="matrix",
                                template=Path(tpl_rel_path),
                                destination=output_file,
                            )
                        )
                        continue
                    with open(output_file, "w") as f:
                        log.debug(f"[bright_black]Rendering [bold]{output_file}")
                        f.write(rendered)

        if exceptions:
            if len(exceptions) == 1:
                raise exceptions[0]
            raise BakeryRenderErrorGroup("One or more template rendering errors occurred", exceptions)

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
