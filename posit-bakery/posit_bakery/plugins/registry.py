import logging
from importlib.metadata import entry_points

from posit_bakery.plugins.protocol import BakeryToolPlugin

log = logging.getLogger(__name__)

_plugins: dict[str, BakeryToolPlugin] | None = None


def discover_plugins() -> dict[str, BakeryToolPlugin]:
    """Load all plugins from the bakery.plugins entry point group.

    After loading plugins, registers any tool options classes they provide
    and rebuilds the config models to support them in bakery.yaml parsing.

    Results are cached after the first call.
    """
    global _plugins
    if _plugins is not None:
        return _plugins

    _plugins = {}
    eps = entry_points(group="bakery.plugins")
    for ep in eps:
        try:
            plugin_cls = ep.load()
            plugin = plugin_cls()
            if not isinstance(plugin, BakeryToolPlugin):
                log.warning(
                    f"Plugin '{ep.name}' from '{ep.value}' does not satisfy BakeryToolPlugin protocol, skipping."
                )
                continue
            _plugins[plugin.name] = plugin
            log.debug(f"Loaded plugin '{plugin.name}' from '{ep.value}'")
        except Exception as e:
            log.warning(f"Failed to load plugin '{ep.name}' from '{ep.value}': {e}")

    # Register tool options from plugins and rebuild config models
    _register_plugin_tool_options()

    return _plugins


def _register_plugin_tool_options() -> None:
    """Register tool options classes from discovered plugins and rebuild config models."""
    from posit_bakery.config.tools.registry import register_tool_options
    from posit_bakery.config.tools import rebuild_tool_models

    registered_any = False
    for plugin in _plugins.values():
        tool_options_class = getattr(plugin, "tool_options_class", None)
        if tool_options_class is not None:
            register_tool_options(plugin.name, tool_options_class)
            registered_any = True

    if registered_any:
        rebuild_tool_models()


def get_plugin(name: str) -> BakeryToolPlugin:
    """Get a specific plugin by name.

    :raises KeyError: If the plugin is not found.
    """
    plugins = discover_plugins()
    if name not in plugins:
        raise KeyError(f"Plugin '{name}' not found. Available plugins: {list(plugins.keys())}")
    return plugins[name]
