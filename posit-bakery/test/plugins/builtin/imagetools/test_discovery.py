"""Tests for imagetools plugin discovery."""

import pytest

from posit_bakery.plugins.registry import discover_plugins
from posit_bakery.plugins.protocol import BakeryToolPlugin

pytestmark = [pytest.mark.unit]


def test_imagetools_plugin_is_discovered():
    plugins = discover_plugins()
    assert "imagetools" in plugins
    assert isinstance(plugins["imagetools"], BakeryToolPlugin)
    assert plugins["imagetools"].name == "imagetools"


def test_legacy_soci_oras_plugins_are_not_registered():
    """The standalone soci/oras plugins were merged into imagetools; they
    should no longer be discovered as separate plugins."""
    plugins = discover_plugins()
    assert "soci" not in plugins
    assert "oras" not in plugins
