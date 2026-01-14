import abc
from typing import Annotated, Literal, ClassVar

from pydantic import ConfigDict, Field
from ruamel.yaml import YAML

from posit_bakery.config.shared import BakeryYAMLModel
from posit_bakery.util import cached_session
from .const import QUARTO_DOWNLOAD_URL, QUARTO_PREVIOUS_VERSIONS_URL, QUARTO_PRERELEASE_URL, SupportedDependencies
from .dependency import DependencyConstraint, DependencyVersions
from .version import DependencyVersion


class QuartoDependency(BakeryYAMLModel, abc.ABC):
    """Quarto depencency definition for bakery configuration.

    :param prerelease: Whether to include prerelease versions. (default: False)"""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    dependency: Literal[SupportedDependencies.QUARTO] = SupportedDependencies.QUARTO

    prerelease: Annotated[
        bool,
        Field(
            default=False,
            description="Whether to include prerelease versions.",
        ),
    ]

    def _fetch_versions(self) -> list[DependencyVersion]:
        """Fetch available Quarto versions.
        Only the latest patch version for each minor version is included.

        This method uses caching to avoid repeated network requests.

        :return: A sorted list of available Quarto versions.
        """
        session = cached_session()

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


class QuartoDependencyVersions(DependencyVersions, QuartoDependency):
    """Class for specifying a list of Quarto versions."""


class QuartoDependencyConstraint(DependencyConstraint, QuartoDependency):
    """Class for specifying a list of Quarto version constraints."""

    VERSIONS_CLASS: ClassVar[type[DependencyVersions]] = QuartoDependencyVersions
