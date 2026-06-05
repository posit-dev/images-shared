import pytest
from pydantic import TypeAdapter, ValidationError

from posit_bakery.config.image.dev_version import (
    DevelopmentVersionField,
    ImageDevelopmentVersionFromDependency,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


_UBUNTU_24_OS = {"name": "Ubuntu 24.04", "primary": True}


class TestImageDevelopmentVersionFromDependency:
    def test_get_version_positron_prerelease(self, patch_requests_get):
        """get_version() resolves via the positron prerelease constraint."""
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            prerelease=True,
            os=[_UBUNTU_24_OS],
        )
        assert dev.get_version() == "2026.07.0-55"

    def test_get_version_positron_stable(self, patch_requests_get):
        """get_version() resolves the latest stable positron version."""
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            prerelease=False,
            os=[_UBUNTU_24_OS],
        )
        version = dev.get_version()
        assert version is not None
        assert "2026.07" not in version  # daily version should not appear

    def test_prerelease_defaults_false(self):
        """prerelease defaults to False when not specified."""
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            os=[_UBUNTU_24_OS],
        )
        assert dev.prerelease is False

    def test_resolve_os_urls_no_artifact_url(self, patch_requests_get):
        """_resolve_os_urls() returns OS entries without setting artifactDownloadURL."""
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            prerelease=True,
            os=[_UBUNTU_24_OS],
        )
        resolved = dev._resolve_os_urls()
        assert len(resolved) == 1
        assert resolved[0].artifactDownloadURL is None

    def test_source_type_discriminator(self):
        """Pydantic resolves sourceType=dependency to this class."""
        adapter = TypeAdapter(DevelopmentVersionField)
        obj = adapter.validate_python(
            {
                "sourceType": "dependency",
                "dependency": "positron",
                "prerelease": True,
                "os": [_UBUNTU_24_OS],
            }
        )
        assert isinstance(obj, ImageDevelopmentVersionFromDependency)

    def test_bad_dependency_rejected(self):
        """An unrecognised dependency name fails Pydantic validation."""
        with pytest.raises(ValidationError):
            ImageDevelopmentVersionFromDependency(
                dependency="not-a-dependency",
                os=[_UBUNTU_24_OS],
            )

    def test_repr(self):
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            prerelease=True,
            os=[_UBUNTU_24_OS],
        )
        assert 'sourceType="dependency"' in repr(dev)
        assert "positron" in repr(dev)
        assert "prerelease=True" in repr(dev)
