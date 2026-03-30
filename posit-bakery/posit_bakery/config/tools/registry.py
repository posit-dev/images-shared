"""Registry for tool option types provided by plugins.

This module is intentionally free of plugin imports to avoid circular dependencies.
Plugins register their ToolOptions subclasses here during discovery, and the config
system reads from here to build the discriminated union for YAML deserialization.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from posit_bakery.config.tools.base import ToolOptions

log = logging.getLogger(__name__)

_tool_options_classes: dict[str, type["ToolOptions"]] = {}


def register_tool_options(name: str, cls: type["ToolOptions"]) -> None:
    """Register a tool options class by name.

    :param name: The tool name (must match the Literal value of the class's `tool` field).
    :param cls: The ToolOptions subclass to register.
    """
    if name in _tool_options_classes:
        log.warning(f"Tool options for '{name}' already registered, overwriting.")
    _tool_options_classes[name] = cls
    log.debug(f"Registered tool options for '{name}': {cls.__name__}")


def get_tool_options_classes() -> dict[str, type["ToolOptions"]]:
    """Return all registered tool options classes."""
    return dict(_tool_options_classes)


def get_tool_options_class(name: str) -> type["ToolOptions"] | None:
    """Get a registered tool options class by name."""
    return _tool_options_classes.get(name)
