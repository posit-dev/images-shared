import abc
from functools import cache
from typing import Annotated, Literal, ClassVar

from pydantic import ConfigDict, Field, field_validator
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

    @staticmethod
    @cache
    def _fetch_versions(prerelease: bool = False) -> list[DependencyVersion]:
        """Fetch available Quarto versions.
        Only the latest patch version for each minor version is included.

        Memoized so the fetch+parse runs once per bakery invocation per
        ``prerelease`` value (at most two entries).

        :return: A sorted list of available Quarto versions.
        """
        session = cached_session()

        versions = []
        # Fetch stable release
        response = session.get(QUARTO_DOWNLOAD_URL)
        response.raise_for_status()
        versions.append(DependencyVersion(response.json().get("version")))

        if prerelease:
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
        return self._fetch_versions(self.prerelease)


class QuartoDependencyVersions(DependencyVersions, QuartoDependency):
    """Class for specifying a list of Quarto versions.

    Only a single version is supported because the quarto deb package
    installs to a flat /opt/quarto/ directory with no version scoping.
    """

    @field_validator("versions", mode="after")
    @classmethod
    def validate_single_version(cls, versions: list[str]) -> list[str]:
        if len(versions) > 1:
            raise ValueError(
                f"Only one Quarto version may be specified (got {len(versions)}). "
                "The quarto apt package installs to a single /opt/quarto/ directory "
                "and cannot coexist with other versions."
            )
        return versions


class QuartoDependencyConstraint(DependencyConstraint, QuartoDependency):
    """Class for specifying a list of Quarto version constraints."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    VERSIONS_CLASS: ClassVar[type[DependencyVersions]] = QuartoDependencyVersions
