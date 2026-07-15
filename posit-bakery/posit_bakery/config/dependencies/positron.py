import abc
from functools import cache
from typing import Annotated, Literal, ClassVar

from pydantic import ConfigDict, Field

from posit_bakery.config.shared import BakeryYAMLModel
from posit_bakery.util import cached_session
from .const import POSITRON_DAILY_URL_TEMPLATE, POSITRON_RELEASES_URL_TEMPLATE, SupportedDependencies
from .dependency import DependencyVersions, DependencyConstraint
from .version import DependencyVersion

# Mapping from Docker TARGETARCH values to Positron CDN architecture path segments.
_ARCH_MAP = {"amd64": "x86_64", "arm64": "arm64"}
_DEFAULT_ARCH = "amd64"


class PositronDependency(BakeryYAMLModel, abc.ABC):
    """Positron dependency definition for bakery configuration."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    dependency: Literal[SupportedDependencies.POSITRON] = SupportedDependencies.POSITRON

    prerelease: Annotated[
        bool,
        Field(
            default=False,
            description="Whether to include the latest daily build.",
        ),
    ]

    @staticmethod
    def releases_url(target_arch: str = _DEFAULT_ARCH) -> str:
        """Return the releases URL for a given TARGETARCH value.

        :param target_arch: Docker TARGETARCH value (amd64 or arm64).
        :return: The fully-qualified releases URL.
        """
        arch = _ARCH_MAP[target_arch]
        return POSITRON_RELEASES_URL_TEMPLATE.format(arch=arch)

    @staticmethod
    def daily_url(target_arch: str = _DEFAULT_ARCH) -> str:
        """Return the daily CDN URL for a given TARGETARCH value.

        :param target_arch: Docker TARGETARCH value (amd64 or arm64).
        :return: The fully-qualified daily releases URL.
        """
        arch = _ARCH_MAP[target_arch]
        return POSITRON_DAILY_URL_TEMPLATE.format(arch=arch)

    @staticmethod
    @cache
    def _fetch_versions(prerelease: bool = False) -> list[DependencyVersion]:
        """Fetch available Positron versions from Posit CDN.

        Uses the default architecture for version discovery since the version
        list is identical across architectures.

        Memoized so the fetch+parse runs once per bakery invocation per
        ``prerelease`` value (at most two entries).

        :return: A sorted list of available Positron versions.
        """
        session = cached_session()
        response = session.get(PositronDependency.releases_url())
        response.raise_for_status()

        releases = response.json().get("releases", [])
        versions = [DependencyVersion(r["version"]) for r in releases]

        if prerelease:
            response = session.get(PositronDependency.daily_url())
            response.raise_for_status()
            data = response.json()
            versions.append(DependencyVersion(data["version"]))

        return sorted(set(versions), reverse=True)

    def available_versions(self) -> list[DependencyVersion]:
        """Return a list of available Positron versions.

        Returns a shallow copy since ``_fetch_versions`` is memoized; callers
        must not mutate the cached list shared across all instances.

        :return: A sorted list of available Positron versions.
        """
        return list(self._fetch_versions(self.prerelease))


class PositronDependencyVersions(DependencyVersions, PositronDependency):
    """Class for specifying a list of Positron versions."""


class PositronDependencyConstraint(DependencyConstraint, PositronDependency):
    """Class for specifying a Positron version constraint."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    VERSIONS_CLASS: ClassVar[type[DependencyVersions]] = PositronDependencyVersions
