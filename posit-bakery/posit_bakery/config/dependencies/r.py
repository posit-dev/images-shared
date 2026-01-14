import abc
from typing import Literal, ClassVar

from pydantic import ConfigDict

from posit_bakery.config.shared import BakeryYAMLModel
from posit_bakery.util import cached_session
from .const import R_VERSIONS_URL, SupportedDependencies
from .dependency import DependencyVersions, DependencyConstraint
from .version import DependencyVersion


class RDependency(BakeryYAMLModel, abc.ABC):
    """R depencency definition for bakery configuration."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    dependency: Literal[SupportedDependencies.R] = SupportedDependencies.R

    def _fetch_versions(self) -> list[DependencyVersion]:
        """Fetch available R versions from Posit.

        This method uses caching to avoid repeated network requests.

        The results exclude "devel" and "next" versions.

        :return: A sorted list of available R versions.
        """
        session = cached_session()
        response = session.get(R_VERSIONS_URL)
        response.raise_for_status()

        versions_data = response.json().get("r_versions", [])
        versions = sorted([DependencyVersion(v) for v in versions_data if v not in ("devel", "next")], reverse=True)

        return versions

    def available_versions(self) -> list[DependencyVersion]:
        """Return a list of available R versions.

        :return: A sorted list of available R versions.
        """
        return self._fetch_versions()


class RDependencyVersions(DependencyVersions, RDependency):
    """Class for specifying a list of R versions."""


class RDependencyConstraint(DependencyConstraint, RDependency):
    """Class for specifying an R version constraint."""

    VERSIONS_CLASS: ClassVar[type[DependencyVersions]] = RDependencyVersions
