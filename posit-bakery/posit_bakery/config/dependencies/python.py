from typing import Literal

from requests_cache import CachedSession

from posit_bakery.config.dependencies.dependency import Dependency
from posit_bakery.config.dependencies.version import DependencyVersion


# All available python versions from astral-sh/python-build-standalone
UV_PYTHON_DOWNLOADS_JSON_URL = (
    "https://raw.githubusercontent.com/astral-sh/uv/refs/heads/main/crates/uv-python/download-metadata.json"
)


class PythonDependency(Dependency):
    """Python depencency definition for bakery configuration."""

    dependency: Literal["python"] = "python"

    def _fetch_versions(self) -> list[DependencyVersion]:
        """Fetch available Python versions from astral-sh/python-build-standalone.

        This method uses caching to avoid repeated network requests.

        The results only include cpython builds for linux.
        Prerelease versions are excluded.

        Versions are de-duplicated across architectures.

        :return: A sorted list of available Python versions.
        """
        session = CachedSession(
            cache_name="bakery_cache", expire_after=3600, backend="filesystem", use_temp=True, allowable_methods=["GET"]
        )
        response = session.get(UV_PYTHON_DOWNLOADS_JSON_URL)
        response.raise_for_status()

        versions_data = response.json().values()
        versions = set(
            [
                f"{v['major']}.{v['minor']}.{v['patch']}"
                for v in versions_data
                if v.get("name") == "cpython" and v.get("os") == "linux" and not v.get("prerelease")
            ]
        )

        return sorted([DependencyVersion(v) for v in versions], reverse=True)

    def available_versions(self) -> list[DependencyVersion]:
        """Return a list of available Python versions.

        :return: A sorted list of available Python versions.
        """
        return self._fetch_versions()
