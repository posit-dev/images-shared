from typing import Annotated, Union

from pydantic import Field

from posit_bakery.config.dependencies._base import Dependency, VersionsConstraint


# DependencyTypes = Union[PythonOptions]
# DependencyField = Annotated[DependencyTypes, Field(discriminator="dependency")]

__all__ = [
    "Dependency",
    "VersionsConstraint",
]
