from typing import Literal, Annotated

from pydantic import Field

from posit_bakery.config.image.build_os import DEFAULT_OS
from posit_bakery.config.image.version_os import ImageVersionOS
from posit_bakery.config.image.dev_version.base import BaseImageDevelopmentVersion
from posit_bakery.config.image.posit_product.const import ProductEnum, ReleaseStreamEnum
from posit_bakery.config.image.posit_product.main import get_product_artifact_by_stream


class ImageDevelopmentVersionFromProductStream(BaseImageDevelopmentVersion):
    """Image development version sourced from a product stream."""

    sourceType: Literal["stream"] = "stream"
    product: Annotated[ProductEnum, Field(description="The ID of the product stream to use for this image version.")]
    stream: Annotated[ReleaseStreamEnum, Field(description="The release stream to use for this image version.")]

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

        :return: The version string from the product stream.
        """
        _os = self.get_primary_os()
        result = get_product_artifact_by_stream(self.product, self.stream, _os.buildOS)

        return result.version

    def get_url_by_os(self, use_arch_placeholder: bool = False) -> dict[str, str]:
        """Retrieve the URL for each OS from the specified product stream.

        Args:
            use_arch_placeholder: If True, returns URLs with __ARCH__ placeholder instead of
                concrete architecture strings. This allows the URL to be resolved at
                container build time based on TARGETARCH. Defaults to False.

        Returns:
            A dictionary mapping OS names to their corresponding URLs.
        """
        url_by_os = {}
        for _os in self.os:
            result = get_product_artifact_by_stream(
                self.product, self.stream, _os.buildOS, use_arch_placeholder=use_arch_placeholder
            )
            url_by_os[_os.name] = str(result.download_url)

        return url_by_os

    def __repr__(self):
        return f'devVersion(sourceType="stream", product="{self.product}", stream="{self.stream}")'
