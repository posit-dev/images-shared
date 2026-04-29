import logging
from typing import Literal, Annotated

import requests
from pydantic import Field, ValidationError

from posit_bakery.config.image.build_os import DEFAULT_OS, DEFAULT_PLATFORMS
from posit_bakery.config.image.dev_version.base import BaseImageDevelopmentVersion
from posit_bakery.config.image.posit_product.const import ProductEnum, ReleaseStreamEnum
from posit_bakery.config.image.posit_product.main import get_product_artifact_by_stream
from posit_bakery.config.image.version_os import ImageVersionOS

log = logging.getLogger(__name__)


class ImageDevelopmentVersionFromProductStream(BaseImageDevelopmentVersion):
    """Image development version sourced from a product stream."""

    sourceType: Literal["stream"] = "stream"
    product: Annotated[ProductEnum, Field(description="The ID of the product stream to use for this image version.")]
    stream: Annotated[ReleaseStreamEnum, Field(description="The release stream to use for this image version.")]
    _resolved_version: str | None = None

    def get_primary_os(self) -> ImageVersionOS:
        """Retrieve the primary OS from the parent image if available.

        :return: The primary OS string.
        """
        for _os in self.os:
            if _os.primary:
                return _os

        return DEFAULT_OS

    def get_version(self) -> str:
        """Retrieve the version from the specified product stream.

        If _resolve_os_urls() has already been called, returns the cached
        version. Otherwise fetches it from the primary OS stream.

        :return: The version string from the product stream.
        """
        if self._resolved_version is not None:
            return self._resolved_version
        _os = self.get_primary_os()
        result = get_product_artifact_by_stream(self.product, self.stream, _os.buildOS)
        return result.version

    def get_url_by_os(self, generalize_architecture: bool = False) -> dict[str, str]:
        """Retrieve the URL for each OS from the specified product stream.

        :return: A dictionary mapping OS names to their corresponding URLs.
        """
        url_by_os = {}
        for _os in self.os:
            result = get_product_artifact_by_stream(self.product, self.stream, _os.buildOS)
            if generalize_architecture:
                url_by_os[_os.name] = str(result.architecture_generalized_download_url)
            else:
                url_by_os[_os.name] = str(result.download_url)

        return url_by_os

    def _resolve_os_urls(self) -> list[ImageVersionOS]:
        """Resolve artifact URLs per-OS, excluding OSes whose platform
        is not yet available in the product stream.

        Caches the version from the first successfully resolved OS so
        that get_version() can return it without a redundant fetch.
        """
        self._resolved_version = None
        resolved = []
        for os_version in self.os:
            try:
                generalize = os_version.platforms != DEFAULT_PLATFORMS
                result = get_product_artifact_by_stream(self.product, self.stream, os_version.buildOS)
                if generalize:
                    os_version.artifactDownloadURL = str(result.architecture_generalized_download_url)
                else:
                    os_version.artifactDownloadURL = str(result.download_url)
                if self._resolved_version is None:
                    self._resolved_version = result.version
                resolved.append(os_version)
            except (ValueError, ValidationError, requests.RequestException) as e:
                log.warning(f"Excluding OS '{os_version.name}' from {repr(self)}: {e}")
        return resolved

    def get_release_stream(self) -> ReleaseStreamEnum:
        """Return the release stream for this product stream development version.

        :return: The configured ReleaseStreamEnum value.
        """
        return self.stream

    def __repr__(self):
        return f'devVersion(sourceType="stream", product="{self.product}", stream="{self.stream}")'
