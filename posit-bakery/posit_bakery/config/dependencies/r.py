from typing import Literal

from posit_bakery.config.dependencies.dependency import Dependency
from posit_bakery.config.dependencies.version import DependencyVersion


class RDependency(Dependency):
    """R depencency definition for bakery configuration."""

    dependency: Literal["R"] = "R"

    def available_versions(self) -> list[DependencyVersion]:
        """Return a list of available R versions."""
        # TODO: Implement fetching
        raise NotImplementedError("Fetching available R versions is not yet implemented.")
