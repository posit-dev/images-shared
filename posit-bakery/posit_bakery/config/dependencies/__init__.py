from typing import Annotated, Union

from pydantic import Field

from posit_bakery.config.dependencies.dependency import Dependency
from posit_bakery.config.dependencies.python import PythonDependency
from posit_bakery.config.dependencies.quarto import QuartoDependency
from posit_bakery.config.dependencies.r import RDependency
from posit_bakery.config.dependencies.version import DependencyVersion, VersionConstraint


DependencyTypes = Union[PythonDependency, RDependency, QuartoDependency]
DependencyField = Annotated[DependencyTypes, Field(discriminator="dependency")]

__all__ = [
    "Dependency",
    "DependencyField",
    "DependencyTypes",
    "PythonDependency",
    "RDependency",
    "QuartoDependency",
    "DependencyVersion",
    "VersionConstraint",
]
