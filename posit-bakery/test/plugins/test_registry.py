import pytest
from unittest.mock import patch, MagicMock
from posit_bakery.plugins.protocol import BakeryToolPlugin
from posit_bakery.plugins.registry import discover_plugins, get_plugin

pytestmark = [pytest.mark.unit]


class TestProtocol:
    def test_protocol_is_runtime_checkable(self):
        """BakeryToolPlugin must be runtime_checkable so we can validate plugins."""
        assert hasattr(BakeryToolPlugin, "__protocol_attrs__") or hasattr(
            BakeryToolPlugin, "__abstractmethods__"
        ), "BakeryToolPlugin should be a Protocol"


class TestDiscoverPlugins:
    def test_discovers_dgoss_plugin(self):
        """discover_plugins should find the dgoss builtin plugin via entry points."""
        plugins = discover_plugins()
        assert "dgoss" in plugins

    def test_returns_dict_of_plugins(self):
        """discover_plugins should return a dict keyed by plugin name."""
        plugins = discover_plugins()
        assert isinstance(plugins, dict)
        for name, plugin in plugins.items():
            assert isinstance(name, str)
            assert hasattr(plugin, "name")
            assert hasattr(plugin, "execute")
            assert hasattr(plugin, "register_cli")


class TestGetPlugin:
    def test_get_existing_plugin(self):
        """get_plugin should return a plugin by name."""
        plugin = get_plugin("dgoss")
        assert plugin.name == "dgoss"

    def test_get_nonexistent_plugin_raises(self):
        """get_plugin should raise KeyError for unknown plugin names."""
        with pytest.raises(KeyError, match="no-such-plugin"):
            get_plugin("no-such-plugin")


from posit_bakery.plugins.builtin.dgoss import DGossPlugin


class TestDGossPlugin:
    def test_satisfies_protocol(self):
        """DGossPlugin must satisfy BakeryToolPlugin protocol."""
        plugin = DGossPlugin()
        assert isinstance(plugin, BakeryToolPlugin)

    def test_has_required_attributes(self):
        """DGossPlugin must have name and description."""
        plugin = DGossPlugin()
        assert plugin.name == "dgoss"
        assert isinstance(plugin.description, str)
        assert len(plugin.description) > 0

    def test_register_cli_creates_command_group(self):
        """register_cli should add a 'dgoss' command group to the app."""
        import typer
        app = typer.Typer()
        plugin = DGossPlugin()
        plugin.register_cli(app)
        # Verify a command group was registered — typer stores registered groups internally
        group_names = [info.name for info in app.registered_groups]
        assert "dgoss" in group_names
