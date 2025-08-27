from typing import Literal

from posit_bakery.config.dependencies.dependency import Dependency
from posit_bakery.config.dependencies.version import DependencyVersion


class PythonDependency(Dependency):
    """Python depencency definition for bakery configuration."""

    dependency: Literal["python"] = "python"

    def available_versions(self) -> list[DependencyVersion]:
        """Return a list of available Python versions."""
        # TODO: Implement fetching
        raise NotImplementedError("Fetching available Python versions is not yet implemented.")
