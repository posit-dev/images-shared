from functools import partial
from typing import Union

from pydantic import Field

from posit_bakery.config.tools.base import ToolOptions
from posit_bakery.config.tools.goss import GossOptions


ToolTypes = Union[GossOptions]
ToolField = partial(Field, discriminator="tool")


def default_tool_options() -> list[ToolOptions]:
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
