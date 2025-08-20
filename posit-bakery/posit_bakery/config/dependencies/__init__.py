from typing import Annotated, Union

from pydantic import Field

from posit_bakery.config.dependencies._base import Dependency
from posit_bakery.config.dependencies.version import VersionConstraint


# DependencyTypes = Union[PythonOptions]
# DependencyField = Annotated[DependencyTypes, Field(discriminator="dependency")]

__all__ = [
    "Dependency",
    "VersionConstraint",
]
