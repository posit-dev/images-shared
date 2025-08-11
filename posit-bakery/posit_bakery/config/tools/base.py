import abc
from typing import Annotated

from pydantic import Field

from posit_bakery.config.shared import BakeryYAMLModel


class ToolOptions(BakeryYAMLModel, abc.ABC):
    """Base class for tool options in the bakery configuration."""

    tool: Annotated[str, Field(description="Name of the tool. Set as a literal in subclasses.")]
