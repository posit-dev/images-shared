import abc
from typing import Literal, ClassVar

from pydantic import ConfigDict

from posit_bakery.config.shared import BakeryYAMLModel
from posit_bakery.util import cached_session
from .const import (
    POSITRON_ARCH_MAP,
    POSITRON_DEFAULT_ARCH,
    POSITRON_RELEASES_URL_TEMPLATE,
    SupportedDependencies,
)
from .dependency import DependencyVersions, DependencyConstraint
from .version import DependencyVersion


class PositronDependency(BakeryYAMLModel, abc.ABC):
    """Positron dependency definition for bakery configuration."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    dependency: Literal[SupportedDependencies.POSITRON] = SupportedDependencies.POSITRON

    @staticmethod
    def releases_url(target_arch: str = POSITRON_DEFAULT_ARCH) -> str:
        """Return the releases URL for a given TARGETARCH value.

        :param target_arch: Docker TARGETARCH value (amd64 or arm64).
        :return: The fully-qualified releases URL.
        """
        arch = POSITRON_ARCH_MAP[target_arch]
        return POSITRON_RELEASES_URL_TEMPLATE.format(arch=arch)

    def _fetch_versions(self) -> list[DependencyVersion]:
        """Fetch available Positron versions from Posit CDN.

        Uses the default architecture for version discovery since the version
        list is identical across architectures.

        This method uses caching to avoid repeated network requests.

        :return: A sorted list of available Positron versions.
        """
        session = cached_session()
        response = session.get(self.releases_url())
        response.raise_for_status()

        releases = response.json().get("releases", [])
        versions = [DependencyVersion(r["version"]) for r in releases]

        return sorted(versions, reverse=True)

    def available_versions(self) -> list[DependencyVersion]:
        """Return a list of available Positron versions.

        :return: A sorted list of available Positron versions.
        """
        return self._fetch_versions()


class PositronDependencyVersions(DependencyVersions, PositronDependency):
    """Class for specifying a list of Positron versions."""


class PositronDependencyConstraint(DependencyConstraint, PositronDependency):
    """Class for specifying a Positron version constraint."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    VERSIONS_CLASS: ClassVar[type[DependencyVersions]] = PositronDependencyVersions
