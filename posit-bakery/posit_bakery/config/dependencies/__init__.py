from typing import Annotated, Union

from pydantic import Field

from .dependency import DependencyVersion
from .python import PythonDependencyConstraint, PythonDependencyVersions
from .quarto import QuartoDependencyConstraint, QuartoDependencyVersions
from .r import RDependencyConstraint, RDependencyVersions


DependencyConstraintField = Annotated[
    Union[PythonDependencyConstraint, RDependencyConstraint, QuartoDependencyConstraint],
    Field(discriminator="dependency"),
]
DependencyVersionsField = Annotated[
    Union[PythonDependencyVersions, RDependencyVersions, QuartoDependencyVersions],
    Field(discriminator="dependency"),
]

__all__ = [
    "DependencyVersion",
    "DependencyConstraintField",
    "DependencyVersionsField",
]
