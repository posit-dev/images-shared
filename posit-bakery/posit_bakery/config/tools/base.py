import abc

from posit_bakery.config.shared import BakeryYAMLModel


class ToolOptions(BakeryYAMLModel, abc.ABC):
    """Base class for tool options in the bakery configuration."""

    tool: str
