"""Discovery of the consolidated imagetools plugin and its soci tool options."""

import pytest

from posit_bakery.config.tools.registry import get_tool_options_classes
from posit_bakery.plugins.builtin.imagetools.options import SociOptions
from posit_bakery.plugins.protocol import BakeryToolPlugin
from posit_bakery.plugins.registry import discover_plugins

pytestmark = [pytest.mark.unit]


def test_imagetools_plugin_is_discovered():
    plugins = discover_plugins()
    assert "imagetools" in plugins
    assert isinstance(plugins["imagetools"], BakeryToolPlugin)
    assert plugins["imagetools"].name == "imagetools"


def test_no_standalone_oras_or_soci_plugins():
    # The oras/soci tooling is owned by the single imagetools plugin now.
    plugins = discover_plugins()
    assert "oras" not in plugins
    assert "soci" not in plugins


def test_soci_tool_options_registered_under_soci():
    # `tool: soci` in bakery.yaml must still resolve to SociOptions even though the imagetools
    # plugin (not a "soci" plugin) provides it.
    discover_plugins()
    assert get_tool_options_classes().get("soci") is SociOptions
