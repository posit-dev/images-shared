from typing import Annotated, Union

from pydantic import Field

from . import const
from .dependency import DependencyVersion, DependencyConstraint, DependencyVersions
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


def get_dependency_versions_class(dependency_name: str) -> type[DependencyVersions]:
    """Get the DependencyVersions class for a given dependency name.

    :param dependency_name: The name of the dependency.
    :return: The corresponding DependencyVersions class.
    :raises ValueError: If the dependency name is not supported.
    """
    mapping = {
        const.SupportedDependencies.PYTHON: PythonDependencyVersions,
        const.SupportedDependencies.R: RDependencyVersions,
        const.SupportedDependencies.QUARTO: QuartoDependencyVersions,
    }

    try:
        return mapping[dependency_name]
    except KeyError as e:
        raise ValueError(f"Unsupported dependency name: {dependency_name}") from e


__all__ = [
    "const",
    "DependencyVersion",
    "DependencyVersions",
    "DependencyConstraint",
    "DependencyConstraintField",
    "DependencyVersionsField",
]
