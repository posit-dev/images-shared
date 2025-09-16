import abc
from typing import Literal, ClassVar

from pydantic import ConfigDict

from .const import UV_PYTHON_DOWNLOADS_JSON_URL
from .dependency import DependencyVersions, DependencyConstraint
from .version import DependencyVersion
from posit_bakery.config.shared import BakeryYAMLModel
from posit_bakery.util import cached_session


class PythonDependency(BakeryYAMLModel, abc.ABC):
    """Python depencency definition for bakery configuration."""

    model_config = ConfigDict(extra="forbid")

    dependency: Literal["python"] = "python"

    def _fetch_versions(self) -> list[DependencyVersion]:
        """Fetch available Python versions from astral-sh/python-build-standalone.

        This method uses caching to avoid repeated network requests.

        The results only include cpython builds for linux.
        Prerelease versions are excluded.

        Versions are de-duplicated across architectures.

        :return: A sorted list of available Python versions.
        """
        session = cached_session()
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


class PythonDependencyVersions(DependencyVersions, PythonDependency):
    """Class for specifying a list of Python versions."""


class PythonDependencyConstraint(DependencyConstraint, PythonDependency):
    """Class for specifying a list of Python version constraints."""

    VERSIONS_CLASS: ClassVar[type[DependencyVersions]] = PythonDependencyVersions
