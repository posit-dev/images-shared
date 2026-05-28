"""Tests for soci plugin discovery."""

import pytest

from posit_bakery.plugins.registry import discover_plugins
from posit_bakery.plugins.protocol import BakeryToolPlugin

pytestmark = [pytest.mark.unit]


def test_soci_plugin_is_discovered():
    plugins = discover_plugins()
    assert "soci" in plugins
    assert isinstance(plugins["soci"], BakeryToolPlugin)
    assert plugins["soci"].name == "soci"
