from typing import Literal

from requests_cache import CachedSession
from ruamel.yaml import YAML

from posit_bakery.config.dependencies.dependency import Dependency
from posit_bakery.config.dependencies.version import DependencyVersion

QUARTO_DOWNLOAD_URL = "https://quarto.org/docs/download/_download.json"
QUARTO_PRERELEASE_URL = "https://quarto.org/docs/download/_prerelease.json"
QUARTO_PREVIOUS_VERSIONS_URL = (
    "https://raw.githubusercontent.com/quarto-dev/quarto-web/refs/heads/main/docs/download/_download-older.yml"
)


class QuartoDependency(Dependency):
    """Quarto depencency definition for bakery configuration.

    :param prerelease: Whether to include prerelease versions. (default: False)"""

    dependency: Literal["quarto"] = "quarto"
    prerelease: bool = False

    def _fetch_versions(self) -> list[DependencyVersion]:
        """Fetch available Quarto versions.
        Only the latest patch version for each minor version is included.

        This method uses caching to avoid repeated network requests.

        :return: A sorted list of available Quarto versions.
        """
        session = CachedSession(
            cache_name="bakery_cache", expire_after=3600, backend="filesystem", use_temp=True, allowable_methods=["GET"]
        )

        versions = []
        # Fetch stable release
        response = session.get(QUARTO_DOWNLOAD_URL)
        response.raise_for_status()
        versions.append(DependencyVersion(response.json().get("version")))

        if self.prerelease:
            # Fetch prerelease version
            response = session.get(QUARTO_PRERELEASE_URL)
            response.raise_for_status()
            versions.append(DependencyVersion(response.json().get("version")))

        # Fetch older versions
        response = session.get(QUARTO_PREVIOUS_VERSIONS_URL)
        response.raise_for_status()
        yaml = YAML()
        versions.extend([DependencyVersion(v.get("title")) for v in yaml.load(response.text)])

        return sorted(versions, reverse=True)

    def available_versions(self) -> list[DependencyVersion]:
        """Return a list of available Quarto version.
        Only the latest patch version for each minor version is included.

        :return: A sorted list of available Quarto versions.
        """
        return self._fetch_versions()
