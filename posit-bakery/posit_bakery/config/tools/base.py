import abc

from posit_bakery.config.shared import BakeryYAMLModel


class ToolOptions(BakeryYAMLModel, abc.ABC):
    tool: str
