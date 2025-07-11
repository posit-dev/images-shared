from posit_bakery.config.tools.base import ToolOptions
from posit_bakery.config.tools.goss import GossOptions


def default_tool_options() -> list[ToolOptions]:
    return [
        GossOptions(),
    ]


__all__ = [
    "ToolOptions",
    "GossOptions",
    "default_tool_options",
]
