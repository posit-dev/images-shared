from typing import Annotated, Literal

from pydantic import Field, field_validator

from posit_bakery.config.dependencies import get_dependency_constraint_class
from posit_bakery.config.dependencies.const import SupportedDependencies
from posit_bakery.config.dependencies.version import VersionConstraint
from posit_bakery.config.image.dev_version.base import BaseImageDevelopmentVersion
from posit_bakery.config.image.posit_product.const import ReleaseChannelEnum
from posit_bakery.config.image.version_os import ImageVersionOS


class ImageDevelopmentVersionFromDependency(BaseImageDevelopmentVersion):
    """Dev version sourced from a dependency constraint.

    When ``prerelease=True``, the dependency's prerelease channel is resolved.
    Version resolution delegates entirely to the dependency module; the
    Containerfile template is responsible for constructing the download URL
    from ``Image.Version`` and any values passed via the ``values`` field.
    """

    sourceType: Literal["dependency"] = "dependency"
    dependency: Annotated[
        SupportedDependencies,
        Field(description="The dependency to resolve a version for."),
    ]
    prerelease: Annotated[
        bool,
        Field(default=False, description="Whether to resolve the dependency's prerelease channel."),
    ] = False
    channel: Annotated[
        ReleaseChannelEnum | None,
        Field(default=None, description="Release channel for this dev version (e.g. 'daily', 'preview')."),
    ] = None

    @field_validator("channel", mode="after")
    @classmethod
    def channel_not_release(cls, v: ReleaseChannelEnum | None) -> ReleaseChannelEnum | None:
        if v == ReleaseChannelEnum.RELEASE:
            raise ValueError(
                "channel: 'release' is not valid for dependency-sourced dev versions. "
                "Omit channel (leave as null) for stable dependency resolution."
            )
        return v

    def get_version(self) -> str:
        constraint_class = get_dependency_constraint_class(self.dependency)
        constraint = constraint_class(
            prerelease=self.prerelease,
            constraint=VersionConstraint(latest=True, count=1),
        )
        result = constraint.resolve_versions()
        return str(result.versions[0])

    def get_url_by_os(self, generalize_architecture: bool = False) -> dict[str, str]:
        return {}

    def _resolve_os_urls(self) -> list[ImageVersionOS]:
        # URL construction is handled by the Containerfile template via values.
        return list(self.os)

    def get_release_channel(self) -> ReleaseChannelEnum | None:
        return self.channel

    def __repr__(self):
        return f'devVersion(sourceType="dependency", dependency="{self.dependency}", prerelease={self.prerelease})'
