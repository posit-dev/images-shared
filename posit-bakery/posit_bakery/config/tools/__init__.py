from typing import Union, Annotated

from pydantic import Field

from posit_bakery.config.tools.base import ToolOptions
from posit_bakery.config.tools.goss import GossOptions


ToolTypes = Union[GossOptions]
ToolField = Annotated[ToolTypes, Field(discriminator="tool")]


def default_tool_options() -> list[ToolOptions]:
    """Return the default tool options for the bakery configuration.

    :return: A list of default tool options.
    """
    return [
        GossOptions(),
    ]


__all__ = [
    "ToolOptions",
    "GossOptions",
    "default_tool_options",
    "ToolTypes",
    "ToolField",
]
