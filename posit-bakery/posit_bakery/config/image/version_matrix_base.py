"""Shared methods for ImageVersion and ImageMatrix."""

import abc
import logging
import re
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any, Union

import jinja2

from posit_bakery.config.registry import BaseRegistry, Registry
from posit_bakery.config.shared import CONTAINERFILE_PREFIX
from posit_bakery.error import BakeryFileError, BakeryRenderError, BakeryRenderErrorGroup, BakeryTemplateError
from .build_os import DEFAULT_PLATFORMS, TargetPlatform
from ..templating import jinja2_env

if TYPE_CHECKING:
    from .variant import ImageVariant
    from .version_os import ImageVersionOS

log = logging.getLogger(__name__)


class VersionMatrixMixin(abc.ABC):
    """Mixin providing shared methods for ImageVersion and ImageMatrix.

    This mixin provides implementations of common properties and methods.
    All fields should be defined in the concrete classes to maintain proper
    field ordering for serialization.
    """

    @classmethod
    @abc.abstractmethod
    def _get_entity_name(cls) -> str:
        """Returns a human-readable name for this entity type.

        :return: 'image version' for ImageVersion, 'image matrix' for ImageMatrix.
        """
        ...

    @abc.abstractmethod
    def _get_version_identifier(self) -> str:
        """Returns the version identifier for error messages.

        :return: The name/version string to use in error messages.
        """
        ...

    @abc.abstractmethod
    def _get_image_template_values(self) -> dict[str, Any]:
        """Returns image-specific template values to add to the Image dict.

        :return: Dictionary with values like Version, IsDevelopmentVersion, etc.
        """
        ...

    @property
    def path(self) -> Path | None:
        """Returns the path to the image version directory.

        :raises ValueError: If the parent image does not have a valid path.
        """
        if self.parent is None or self.parent.path is None:
            raise ValueError("Parent image must resolve a valid path.")
        return Path(self.parent.path) / Path(self.subpath)

    @property
    def all_registries(self) -> list[Registry | BaseRegistry]:
        """Returns the merged registries for this image version.

        :return: A list of registries that includes the overrideRegistries or the version's extraRegistries and any
            registries from the parent image.
        """
        if self.overrideRegistries:
            return deepcopy(self.overrideRegistries)

        all_registries = deepcopy(self.extraRegistries)
        if self.parent is not None:
            for registry in self.parent.all_registries:
                if registry not in all_registries:
                    all_registries.append(registry)

        return all_registries

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
        if self.parent is None:
            raise ValueError("Parent image must be set before generating template values.")

        values: dict[str, Any] = {
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

        # Add subclass-specific Image values (Version, IsDevelopmentVersion, etc.)
        values["Image"].update(self._get_image_template_values())

        if variant is not None:
            values["Image"]["Variant"] = variant.name
        if version_os is not None:
            values["Image"]["OS"] = {
                "Name": version_os.buildOS.name,
                "Family": version_os.buildOS.family.value,
                "Version": version_os.buildOS.version,
                "Codename": version_os.buildOS.codename,
            }
            if version_os.artifactDownloadURL is not None:
                values["Image"]["DownloadURL"] = str(version_os.artifactDownloadURL)
        if self.values:
            values.update(self.values)

        return values

    def render_files(
        self,
        variants: list["ImageVariant"] | None = None,
        regex_filters: list[str] | None = None,
    ):
        """Render files from the template.

        :param variants: Optional list of ImageVariant objects to render Containerfiles for each variant.
        :param regex_filters: Optional list of regex patterns to filter which templates to render.

        :raises BakeryFileError: If the template path does not exist.
        :raises BakeryRenderError: If a template fails to render.
        :raises BakeryRenderErrorGroup: If multiple templates fail to render.
        """
        if self.parent is None:
            raise ValueError("Parent image must be set before rendering files.")

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
        for root, _dirs, files in self.parent.template_path.walk():
            for file in files:
                tpl_full_path = (Path(root) / file).resolve()
                tpl_rel_path = str(tpl_full_path.relative_to(self.parent.template_path))

                # Fixed regex filter logic - skip file if it doesn't match ANY filter
                if regex_filters:
                    if not any(re.match(regex, tpl_rel_path) for regex in regex_filters):
                        log.debug(f"Skipping template [bright_black]{tpl_rel_path}[/] due to regex filters")
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
                            version=self._get_version_identifier(),
                            template=Path(tpl_full_path),
                        )
                    )
                    continue

                # Enable trim_blocks for Containerfile templates
                render_kwargs = {}
                if tpl_rel_path.startswith(CONTAINERFILE_PREFIX):
                    render_kwargs["trim_blocks"] = True

                # If variants are specified, render Containerfile for each variant
                if tpl_rel_path.startswith(CONTAINERFILE_PREFIX) and variants:
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
                                f"{self._get_entity_name()} '{self._get_version_identifier()}' variant '{variant.name}'"
                            )
                            exceptions.append(
                                BakeryRenderError(
                                    cause=e,
                                    context=self.parent.parent.path,
                                    image=self.parent.name,
                                    version=self._get_version_identifier(),
                                    variant=variant.name,
                                    template=Path(tpl_full_path),
                                    destination=Path(containerfile),
                                )
                            )
                            continue
                        containerfile.write_text(rendered)
                        log.debug(f"[bright_black]Rendering [bold]{containerfile}")

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
                            f"Failed to render template [bold]{tpl_rel_path}[/] for image '{self.parent.name}' "
                            f"{self._get_entity_name()} '{self._get_version_identifier()}'"
                        )
                        exceptions.append(
                            BakeryRenderError(
                                cause=e,
                                context=self.parent.parent.path,
                                image=self.parent.name,
                                version=self._get_version_identifier(),
                                template=Path(tpl_rel_path),
                                destination=output_file,
                            )
                        )
                        continue
                    output_file.write_text(rendered)
                    log.debug(f"[bright_black]Rendering [bold]{output_file}")

        if exceptions:
            if len(exceptions) == 1:
                raise exceptions[0]
            raise BakeryRenderErrorGroup("One or more template rendering errors occurred", exceptions)


# For backwards compatibility, also export as BaseVersionMatrix
BaseVersionMatrix = VersionMatrixMixin
