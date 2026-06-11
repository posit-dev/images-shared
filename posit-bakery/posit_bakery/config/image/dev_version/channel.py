import logging
from typing import Literal, Annotated

import requests
from pydantic import Field, ValidationError, model_validator

from posit_bakery.config.image.build_os import DEFAULT_OS, DEFAULT_PLATFORMS
from posit_bakery.config.image.dev_version.base import BaseImageDevelopmentVersion
from posit_bakery.config.image.posit_product.const import ProductEnum, ReleaseChannelEnum
from posit_bakery.config.image.posit_product.main import get_product_artifact_by_channel
from posit_bakery.config.image.version_os import ImageVersionOS

log = logging.getLogger(__name__)


class ImageDevelopmentVersionFromProductChannel(BaseImageDevelopmentVersion):
    """Image development version sourced from a product release channel."""

    sourceType: Literal["stream"] = "stream"
    product: Annotated[ProductEnum, Field(description="The ID of the product channel to use for this image version.")]
    channel: Annotated[
        ReleaseChannelEnum,
        Field(description="The release channel to use for this image version (e.g. 'daily', 'preview')."),
    ]
    resolved_version: Annotated[
        str | None,
        Field(
            exclude=True,
            default=None,
            description="Cached version from the last _resolve_os_urls() call. Avoids a redundant channel fetch in "
            "get_version().",
        ),
    ]
    resolved_channel_latest: Annotated[
        bool,
        Field(
            exclude=True,
            default=True,
            description="Whether the resolved version equals the current channel head. "
            "Populated by _resolve_os_urls(); used to suppress floating {{ Channel }} tags "
            "for builds targeting older versions.",
        ),
    ]
    version_override: Annotated[
        str | None,
        Field(
            exclude=True,
            default=None,
            description="Version pinned by a workflow dispatch spec. When set, bypasses CDN "
            "discovery and is forwarded to the channel resolver for offline template rendering "
            "(PPM) or manifest assertion (Connect, Workbench).",
        ),
    ]
    release_branch: Annotated[
        str | None,
        Field(
            exclude=True,
            default=None,
            description="Release branch for Workbench daily URL construction. "
            "Passed as release_branch to get_product_artifact_by_channel(). "
            "Defaults to 'latest' when None.",
        ),
    ]

    @model_validator(mode="before")
    @classmethod
    def migrate_stream_to_channel(cls, data: dict) -> dict:
        if "stream" in data and "channel" not in data:
            log.warning("devVersions: 'stream' is deprecated in bakery.yaml, use 'channel' instead.")
            data = dict(data)
            data["channel"] = data.pop("stream")
        return data

    def get_primary_os(self) -> ImageVersionOS:
        """Retrieve the primary OS from the parent image if available.

        :return: The primary OS string.
        """
        for _os in self.os:
            if _os.primary:
                return _os

        return DEFAULT_OS

    def get_version(self) -> str:
        """Retrieve the version from the specified product channel.

        If version_override is set, returns it immediately without a network call.
        If _resolve_os_urls() has already been called, returns the cached
        version. Otherwise fetches it from the primary OS channel.

        :return: The version string from the product channel.
        """
        if self.version_override is not None:
            return self.version_override
        if self.resolved_version is not None:
            return self.resolved_version
        _os = self.get_primary_os()
        result = get_product_artifact_by_channel(
            self.product,
            self.channel,
            _os.buildOS,
            release_branch=self.release_branch or "latest",
        )
        return result.version

    def get_url_by_os(self, generalize_architecture: bool = False) -> dict[str, str]:
        """Retrieve the URL for each OS from the specified product channel.

        :return: A dictionary mapping OS names to their corresponding URLs.
        """
        url_by_os = {}
        for _os in self.os:
            result = get_product_artifact_by_channel(
                self.product,
                self.channel,
                _os.buildOS,
                version_override=self.version_override,
                release_branch=self.release_branch or "latest",
            )
            if generalize_architecture:
                url_by_os[_os.name] = str(result.architecture_generalized_download_url)
            else:
                url_by_os[_os.name] = str(result.download_url)

        return url_by_os

    def _resolve_os_urls(self) -> list[ImageVersionOS]:
        """Resolve artifact URLs per-OS, excluding OSes whose platform
        is not yet available in the product channel.

        Caches the version and channel_latest flag from the first successfully
        resolved OS so that get_version() can return them without a redundant fetch.
        """
        # Local import avoids a circular import between channel.py and main.py.
        from posit_bakery.config.image.posit_product.errors import (
            ArtifactNotAvailableError,
            VersionSubstitutionError,
        )

        self.resolved_version = None
        self.resolved_channel_latest = True
        resolved = []
        for os_version in self.os:
            try:
                generalize = os_version.platforms != DEFAULT_PLATFORMS
                result = get_product_artifact_by_channel(
                    self.product,
                    self.channel,
                    os_version.buildOS,
                    version_override=self.version_override,
                    release_branch=self.release_branch or "latest",
                )
                if generalize:
                    os_version.artifactDownloadURL = str(result.architecture_generalized_download_url)
                else:
                    os_version.artifactDownloadURL = str(result.download_url)
                if self.resolved_version is None:
                    self.resolved_version = result.version
                    self.resolved_channel_latest = result.channel_latest
                resolved.append(os_version)
            except (ArtifactNotAvailableError, VersionSubstitutionError):
                raise
            except (ValueError, ValidationError, requests.RequestException) as e:
                log.warning(f"Excluding OS '{os_version.name}' from {repr(self)}: {e}")
        return resolved

    def as_image_version(self):
        """Convert to a standard image version, adding channel_latest to metadata."""
        # Local import mirrors the pattern in base.py to avoid any circular-import risk.
        from posit_bakery.config.image.version import ImageVersion

        resolved_os = self._resolve_os_urls()
        if not resolved_os:
            raise RuntimeError(f"No OSes could be resolved for {repr(self)}")

        version = self.get_version()
        metadata = {"channel_latest": self.resolved_channel_latest}
        release_channel = self.get_release_channel()
        if release_channel is not None:
            metadata["release_channel"] = release_channel
        return ImageVersion(
            name=version,
            subpath=f".dev-{version}".replace(" ", "-").lower(),
            parent=self.parent,
            extraRegistries=self.extraRegistries,
            overrideRegistries=self.overrideRegistries,
            os=resolved_os,
            values=self.values,
            latest=False,
            dependencies=self.parent.resolve_dependency_versions(),
            ephemeral=True,
            isDevelopmentVersion=True,
            metadata=metadata,
        )

    def get_release_channel(self) -> ReleaseChannelEnum:
        """Return the release channel for this product channel development version.

        :return: The configured ReleaseChannelEnum value.
        """
        return self.channel

    def __repr__(self):
        return f'devVersion(sourceType="stream", product="{self.product}", channel="{self.channel}")'
