import os
from pathlib import Path

import pytest

from posit_bakery.config.config import BakeryConfigDocument


class TestBakeryConfigDocument:
    def test_required_fields(self):
        """Test that a BakeryConfigDocument can be created with only the required fields."""
        base_path = Path(os.getcwd())
        d = BakeryConfigDocument(base_path=base_path, repository={"url": "https://example.com/repo"})
        assert d.base_path == base_path
        assert d.path == base_path
        assert str(d.repository.url) == "https://example.com/repo"
        assert len(d.registries) == 0
        assert len(d.images) == 0

    def test_valid(self):
        """Test creating a valid BakeryConfigDocument with all fields."""
        base_path = Path(os.getcwd())
        d = BakeryConfigDocument(
            base_path=base_path,
            repository={"url": "https://example.com/repo"},
            registries=[{"host": "registry.example.com", "namespace": "namespace"}],
            images=[{"name": "my-image", "versions": [{"name": "1.0.0"}]}],
        )

        assert d.base_path == base_path
        assert str(d.repository.url) == "https://example.com/repo"
        assert len(d.registries) == 1
        assert d.registries[0].host == "registry.example.com"
        assert d.registries[0].namespace == "namespace"
        assert len(d.images) == 1
        assert d.images[0].name == "my-image"
        assert len(d.images[0].versions) == 1
        assert d.images[0].versions[0].name == "1.0.0"
        assert len(d.images[0].variants) == 2
        assert d.images[0].variants[0].name == "Standard"
        assert d.images[0].variants[1].name == "Minimal"

    def test_deduplicate_registries(self, caplog):
        """Test that duplicate registries are deduplicated."""
        base_path = Path(os.getcwd())
        d = BakeryConfigDocument(
            base_path=base_path,
            repository={"url": "https://example.com/repo"},
            registries=[
                {"host": "registry.example.com", "namespace": "namespace"},
                {"host": "registry.example.com", "namespace": "namespace"},  # Duplicate
            ],
        )
        assert len(d.registries) == 1
        assert d.registries[0].host == "registry.example.com"
        assert d.registries[0].namespace == "namespace"
        assert "WARNING" in caplog.text
        assert "Duplicate registry defined in config: registry.example.com/namespace" in caplog.text

    def test_check_images_not_empty(self, caplog):
        """Test that a warning is logged if no images are defined."""
        base_path = Path(os.getcwd())
        d = BakeryConfigDocument(base_path=base_path, repository={"url": "https://example.com/repo"})
        assert len(d.images) == 0
        assert "WARNING" in caplog.text
        assert "No images found in the Bakery config. At least one image is required for most commands." in caplog.text

    def test_check_image_duplicates(self):
        """Test that an error is raised if duplicate image names are found."""
        base_path = Path(os.getcwd())
        with pytest.raises(ValueError, match="Duplicate image names found in the bakery config:"):
            BakeryConfigDocument(
                base_path=base_path,
                repository={"url": "https://example.com/repo"},
                images=[
                    {"name": "my-image"},
                    {"name": "my-image"},  # Duplicate
                ],
            )

    def test_resolve_parentage(self):
        """Test that the parent field is set correctly."""
        base_path = Path(os.getcwd())
        d = BakeryConfigDocument(
            base_path=base_path,
            repository={"url": "https://example.com/repo"},
            images=[{"name": "my-image"}],
        )
        assert d.images[0].parent is d

    def test_path(self):
        """Test that the path property returns the base path."""
        base_path = Path(os.getcwd())
        d = BakeryConfigDocument(base_path=base_path, repository={"url": "https://example.com/repo"})
        assert d.path == base_path

    def test_get_image(self):
        """Test that get_image returns the correct image."""
        base_path = Path(os.getcwd())
        d = BakeryConfigDocument(
            base_path=base_path,
            repository={"url": "https://example.com/repo"},
            images=[{"name": "my-image"}],
        )
        image = d.get_image("my-image")
        assert image is not None
        assert image.name == "my-image"

        # Test for a non-existent image
        assert d.get_image("non-existent") is None

    def test_create_image(self):
        """Test that create_image adds a new image to the config."""
        base_path = Path(os.getcwd())
        d = BakeryConfigDocument(base_path=base_path, repository={"url": "https://example.com/repo"})
        new_image = d.create_image("new-image")
        assert new_image.name == "new-image"
        assert len(d.images) == 1
        assert d.images[0] is new_image
        assert new_image.parent is d


class TestBakeryConfig:
    pass
