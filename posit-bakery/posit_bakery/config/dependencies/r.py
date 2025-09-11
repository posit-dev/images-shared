import abc
from typing import Literal

from requests_cache import CachedSession

from .dependency import DependencyVersions, DependencyConstraint
from .version import DependencyVersion

# All available R versions from Posit
R_VERSIONS_URL = "https://cdn.posit.co/r/versions.json"


class RDependency(abc.ABC):
    """R depencency definition for bakery configuration."""

    def _fetch_versions(self) -> list[DependencyVersion]:
        """Fetch available R versions from Posit.

        This method uses caching to avoid repeated network requests.

        The results exclude "devel" and "next" versions.

        :return: A sorted list of available R versions.
        """
        session = CachedSession(
            cache_name="bakery_cache", expire_after=3600, backend="filesystem", use_temp=True, allowable_methods=["GET"]
        )
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


class RDependencyConstraint(DependencyConstraint, RDependency):
    """Class for specifying an R version constraint."""

    dependency: Literal["R"] = "R"


class RDependencyVersions(DependencyVersions, RDependency):
    """Class for specifying a list of R versions."""

    dependency: Literal["R"] = "R"
