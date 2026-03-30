import logging
from importlib.metadata import entry_points

from posit_bakery.plugins.protocol import BakeryToolPlugin

log = logging.getLogger(__name__)

_plugins: dict[str, BakeryToolPlugin] | None = None


def discover_plugins() -> dict[str, BakeryToolPlugin]:
    """Load all plugins from the bakery.plugins entry point group.

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

    return _plugins


def get_plugin(name: str) -> BakeryToolPlugin:
    """Get a specific plugin by name.

    :raises KeyError: If the plugin is not found.
    """
    plugins = discover_plugins()
    if name not in plugins:
        raise KeyError(f"Plugin '{name}' not found. Available plugins: {list(plugins.keys())}")
    return plugins[name]
