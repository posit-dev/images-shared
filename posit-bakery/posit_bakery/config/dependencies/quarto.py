from typing import Literal

from posit_bakery.config.dependencies.dependency import Dependency
from posit_bakery.config.dependencies.version import DependencyVersion


class QuartoDependency(Dependency):
    """Python depencency definition for bakery configuration."""

    dependency: Literal["quarto"] = "quarto"

    def available_versions(self) -> list[DependencyVersion]:
        """Return a list of available Quarto version."""
        # TODO: Implement fetching
        raise NotImplementedError("Fetching available Quarto versions is not yet implemented.")
