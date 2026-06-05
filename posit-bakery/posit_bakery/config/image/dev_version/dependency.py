from typing import Annotated, Literal

from pydantic import Field

from posit_bakery.config.dependencies import get_dependency_constraint_class
from posit_bakery.config.dependencies.const import SupportedDependencies
from posit_bakery.config.dependencies.version import VersionConstraint
from posit_bakery.config.image.dev_version.base import BaseImageDevelopmentVersion
from posit_bakery.config.image.version_os import ImageVersionOS


class ImageDevelopmentVersionFromDependencyPrerelease(BaseImageDevelopmentVersion):
    """Dev version sourced from the prerelease channel of a dependency constraint.

    The dependency's constraint class must support ``prerelease=True``. Version
    resolution delegates entirely to the dependency module; the Containerfile
    template is responsible for constructing the download URL from Image.Version
    and any values passed via the ``values`` field.
    """

    sourceType: Literal["dependency-prerelease"] = "dependency-prerelease"
    dependency: Annotated[
        SupportedDependencies,
        Field(description="The dependency whose prerelease version to resolve."),
    ]

    def get_version(self) -> str:
        constraint_class = get_dependency_constraint_class(self.dependency)
        constraint = constraint_class(
            prerelease=True,
            constraint=VersionConstraint(latest=True, count=1),
        )
        result = constraint.resolve_versions()
        return str(result.versions[0])

    def get_url_by_os(self, generalize_architecture: bool = False) -> dict[str, str]:
        return {}

    def _resolve_os_urls(self) -> list[ImageVersionOS]:
        # URL construction is handled by the Containerfile template via values.
        return list(self.os)

    def __repr__(self):
        return f'devVersion(sourceType="dependency-prerelease", dependency="{self.dependency}")'
