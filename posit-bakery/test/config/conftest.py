from typing import Any

import pytest

from posit_bakery.config import ImageVariant


@pytest.fixture
def common_image_variants_objects() -> list[dict[str, Any]]:
    """Return pure python objects as the default image variants for testing."""
    return [
        ImageVariant(name="Standard", extension="std", tagDisplayName="std", primary=True),
        ImageVariant(name="Minimal", extension="min", tagDisplayName="min"),
    ]


@pytest.fixture
def common_image_variants(common_image_variants_objects) -> list[dict[str, Any]]:
    """Return pure python objects as the default image variants for testing."""
    return [variant.model_dump() for variant in common_image_variants_objects]
