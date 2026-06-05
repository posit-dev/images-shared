import pytest
from pydantic import TypeAdapter, ValidationError

from posit_bakery.config.image.dev_version import (
    DevelopmentVersionField,
    ImageDevelopmentVersionFromDependencyPrerelease,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


_UBUNTU_24_OS = {"name": "Ubuntu 24.04", "primary": True}


class TestImageDevelopmentVersionFromDependencyPrerelease:
    def test_get_version_positron(self, patch_requests_get):
        """get_version() resolves via the positron prerelease constraint."""
        dev = ImageDevelopmentVersionFromDependencyPrerelease(
            dependency="positron",
            os=[_UBUNTU_24_OS],
        )
        assert dev.get_version() == "2026.07.0-55"

    def test_resolve_os_urls_no_artifact_url(self, patch_requests_get):
        """_resolve_os_urls() returns OS entries without setting artifactDownloadURL."""
        dev = ImageDevelopmentVersionFromDependencyPrerelease(
            dependency="positron",
            os=[_UBUNTU_24_OS],
        )
        resolved = dev._resolve_os_urls()
        assert len(resolved) == 1
        assert resolved[0].artifactDownloadURL is None

    def test_source_type_discriminator(self):
        """Pydantic resolves sourceType=dependency-prerelease to this class."""
        adapter = TypeAdapter(DevelopmentVersionField)
        obj = adapter.validate_python(
            {"sourceType": "dependency-prerelease", "dependency": "positron", "os": [_UBUNTU_24_OS]}
        )
        assert isinstance(obj, ImageDevelopmentVersionFromDependencyPrerelease)

    def test_bad_dependency_rejected(self):
        """An unrecognised dependency name fails Pydantic validation."""
        with pytest.raises(ValidationError):
            ImageDevelopmentVersionFromDependencyPrerelease(
                dependency="not-a-dependency",
                os=[_UBUNTU_24_OS],
            )

    def test_repr(self):
        dev = ImageDevelopmentVersionFromDependencyPrerelease(
            dependency="positron",
            os=[_UBUNTU_24_OS],
        )
        assert "dependency-prerelease" in repr(dev)
        assert "positron" in repr(dev)
