"""Shared tests for ImageVersion and ImageMatrix.

Both classes implement similar interfaces for path resolution, platform support,
and template rendering. These tests verify that behavior is consistent across
both implementations.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from posit_bakery.config import BakeryConfigDocument, Image, ImageVersion
from posit_bakery.config.image.build_os import DEFAULT_PLATFORMS
from posit_bakery.config.image.matrix import ImageMatrix
from posit_bakery.error import BakeryFileError, BakeryRenderError, BakeryRenderErrorGroup


pytestmark = [pytest.mark.unit, pytest.mark.config]


class VersionMatrixFactory:
    """Factory for creating ImageVersion or ImageMatrix instances with consistent interfaces."""

    @staticmethod
    def create_version(**kwargs):
        """Create an ImageVersion instance."""
        defaults = {"name": "1.0.0"}
        defaults.update(kwargs)
        return ImageVersion(**defaults)

    @staticmethod
    def create_matrix(**kwargs):
        """Create an ImageMatrix instance."""
        defaults = {"values": {"go_version": ["1.24"]}}
        defaults.update(kwargs)
        return ImageMatrix(**defaults)


@pytest.fixture(params=["version", "matrix"])
def version_or_matrix_factory(request):
    """Parametrized fixture that returns a factory function for either ImageVersion or ImageMatrix."""
    if request.param == "version":
        return VersionMatrixFactory.create_version
    return VersionMatrixFactory.create_matrix


class TestPathResolution:
    """Tests for path property behavior shared by ImageVersion and ImageMatrix."""

    def test_path_raises_when_no_parent(self, version_or_matrix_factory):
        """Path property raises ValueError when parent is None."""
        instance = version_or_matrix_factory()
        with pytest.raises(ValueError, match="Parent image must resolve a valid path"):
            _ = instance.path

    def test_path_raises_when_parent_has_no_path(self, version_or_matrix_factory):
        """Path property raises ValueError when parent.path is None."""
        mock_parent = MagicMock(spec=Image)
        mock_parent.path = None
        instance = version_or_matrix_factory(parent=mock_parent)
        with pytest.raises(ValueError, match="Parent image must resolve a valid path"):
            _ = instance.path


class TestSupportedPlatforms:
    """Tests for supported_platforms property behavior shared by ImageVersion and ImageMatrix."""

    def test_returns_default_platforms_when_no_os(self, version_or_matrix_factory):
        """Returns DEFAULT_PLATFORMS when os list is empty."""
        instance = version_or_matrix_factory(os=[])
        assert instance.supported_platforms == DEFAULT_PLATFORMS


class TestRenderFiles:
    """Tests for render_files method behavior shared by ImageVersion and ImageMatrix."""

    def test_raises_when_template_path_missing(self, version_or_matrix_factory):
        """Raises BakeryFileError when template path doesn't exist."""
        mock_config_parent = MagicMock(spec=BakeryConfigDocument)
        mock_config_parent.path = Path("/nonexistent/path")

        mock_image_parent = MagicMock(spec=Image)
        mock_image_parent.path = Path("/nonexistent/path/test-image")
        mock_image_parent.name = "test-image"
        mock_image_parent.template_path = Path("/nonexistent/path/test-image/template")
        mock_image_parent.parent = mock_config_parent

        instance = version_or_matrix_factory(
            parent=mock_image_parent,
            os=[{"name": "Ubuntu 22.04", "primary": True}],
        )

        with pytest.raises(BakeryFileError, match="template path does not exist"):
            instance.render_files()

    def test_handles_template_syntax_errors(self, get_tmpcontext, version_or_matrix_factory):
        """Raises BakeryRenderError or BakeryRenderErrorGroup on template syntax errors."""
        context = get_tmpcontext("basic")
        mock_parent = MagicMock(spec=BakeryConfigDocument)
        mock_parent.path = context

        image = Image(
            name="test-image",
            versions=[{"name": "1.0.0"}],
            variants=[{"name": "Standard", "extension": "std"}],
            parent=mock_parent,
        )

        # Create a template with invalid Jinja2 syntax
        template_path = context / "test-image" / "template"
        bad_template = template_path / "bad_template.jinja2"
        bad_template.write_text("{{ invalid syntax {% endfor %}")

        instance = version_or_matrix_factory(
            parent=image,
            os=[{"name": "Ubuntu 22.04", "primary": True}],
        )

        with pytest.raises((BakeryRenderError, BakeryRenderErrorGroup)):
            instance.render_files(image.variants)

    def test_single_error_raises_render_error_not_group(self, get_tmpcontext, version_or_matrix_factory):
        """A single render error raises BakeryRenderError, not BakeryRenderErrorGroup."""
        context = get_tmpcontext("basic")
        mock_parent = MagicMock(spec=BakeryConfigDocument)
        mock_parent.path = context

        image = Image(
            name="test-image",
            versions=[{"name": "1.0.0"}],
            variants=[{"name": "Standard", "extension": "std"}],
            parent=mock_parent,
        )

        # Remove all existing templates
        template_path = context / "test-image" / "template"
        for f in template_path.glob("**/*"):
            if f.is_file():
                f.unlink()

        # Create exactly one bad template
        bad_template = template_path / "single_bad.jinja2"
        bad_template.write_text("{{ undefined_variable }}")

        instance = version_or_matrix_factory(parent=image)

        with pytest.raises(BakeryRenderError):
            instance.render_files()
