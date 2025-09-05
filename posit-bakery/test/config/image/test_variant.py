from unittest.mock import MagicMock

import pytest
from _pytest.mark import ParameterSet
from pydantic import ValidationError

from posit_bakery.config import ImageVariant, Image
from posit_bakery.config.tools import GossOptions

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


class TestImageVariant:
    def test_name_required(self, caplog):
        """Test that an ImageVariant object requires a name."""
        with pytest.raises(ValidationError, match="Field required"):
            ImageVariant()
        assert "WARNING" not in caplog.text

    def test_valid(self):
        """Test creating a valid ImageVariant object does not raise an exception."""
        i = ImageVariant(name="Variant 1")

        assert i.parent is None
        assert i.name == "Variant 1"
        assert not i.primary
        assert i.extension == "variant1"
        assert i.tagDisplayName == "variant-1"
        assert len(i.tagPatterns) == 0
        assert len(i.options) == 1

    def test_custom_options(self):
        """Test creating an ImageVariant with custom options."""
        custom_options = [{"tool": "goss", "wait": 10, "command": "/bin/bash -c 'my command'"}]
        i = ImageVariant(name="Custom Goss", options=custom_options)

        assert len(i.options) == 1
        assert i.options[0].tool == "goss"
        assert i.options[0].wait == 10
        assert i.options[0].command == "/bin/bash -c 'my command'"

    def test_unknown_options(self):
        """Test creating an ImageVariant with unknown options raises an exception."""
        with pytest.raises(ValidationError):
            ImageVariant(name="Invalid Variant", options=[{"tool": "unknown_tool"}])

    def test_extension_validation(self):
        """Test that the extension field only allows alphanumeric characters, underscores, and hyphens."""
        with pytest.raises(ValidationError):
            ImageVariant(name="Standard", extension="invalid_extension!")

    def test_tag_display_name_validation(self):
        """Test that the tagDisplayName field only allows alphanumeric characters, underscores, hyphens, and periods."""
        with pytest.raises(ValidationError):
            ImageVariant(name="Standard", tagDisplayName="invalid tag name!")

    @staticmethod
    def tool_option_test_params() -> list[ParameterSet]:
        return [
            pytest.param(
                "goss",
                [],
                [],
                {"wait": 0, "command": "sleep infinity"},
                id="defaults",
            ),
            pytest.param(
                "goss",
                [{"tool": "goss", "wait": 5, "command": "command"}],
                [],
                {"wait": 5, "command": "command"},
                id="parent_overrides_defaults",
            ),
            pytest.param(
                "goss",
                [{"tool": "goss", "wait": 5, "command": "command"}],
                [{"tool": "goss", "wait": 10, "command": "other_command"}],
                {"wait": 10, "command": "other_command"},
                id="variant_overrides_parent",
            ),
            pytest.param(
                "goss",
                [{"tool": "goss", "wait": 5, "command": "command"}],
                [{"tool": "goss", "wait": 0, "command": "sleep infinity"}],
                {"wait": 0, "command": "sleep infinity"},
                id="variant_explicit_default",
            ),
        ]

    @pytest.mark.parametrize("tool_name,parent_tool_options,tool_options,expected_values", tool_option_test_params())
    def test_get_tool_option(self, tool_name, parent_tool_options, tool_options, expected_values):
        """Test that get_tool_option returns the correct tool options."""
        parent_image = MagicMock(spec=Image)
        parent_image.options = parent_tool_options
        parent_image.get_tool_option.return_value = (
            GossOptions(**parent_tool_options[0]) if parent_tool_options else None
        )

        # Must be done this way as options will not appear in model_fields_set if not set during instantiation.
        if tool_options:
            i = ImageVariant(name="test", parent=parent_image, options=tool_options)
        else:
            i = ImageVariant(name="test", parent=parent_image)

        options = i.get_tool_option(tool_name)
        for key, value in expected_values.items():
            assert getattr(options, key) == value
