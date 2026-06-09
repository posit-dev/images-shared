from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import TypeAdapter, ValidationError

from posit_bakery.config import Image, BaseRegistry
from posit_bakery.config.image.dev_version import (
    DevelopmentVersionField,
    ImageDevelopmentVersionFromDependency,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]

_UBUNTU_24_OS = {"name": "Ubuntu 24.04", "primary": True}
_UBUNTU_22_OS = {"name": "Ubuntu 22.04"}


def _mock_parent():
    parent = MagicMock(spec=Image)
    parent.path = Path("/tmp/test")
    parent.resolve_dependency_versions.return_value = []
    return parent


class TestValidation:
    def test_dependency_required(self):
        """dependency is a required field."""
        with pytest.raises(ValidationError, match="Field required"):
            ImageDevelopmentVersionFromDependency(os=[_UBUNTU_24_OS])

    def test_bad_dependency_rejected(self):
        """Unrecognised dependency name fails Pydantic validation."""
        with pytest.raises(ValidationError):
            ImageDevelopmentVersionFromDependency(
                dependency="not-a-real-dependency",
                os=[_UBUNTU_24_OS],
            )

    def test_prerelease_defaults_false(self):
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            os=[_UBUNTU_24_OS],
        )
        assert dev.prerelease is False

    def test_source_type_is_dependency(self):
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            os=[_UBUNTU_24_OS],
        )
        assert dev.sourceType == "dependency"

    def test_source_type_discriminator(self):
        """Pydantic resolves sourceType=dependency to this class via the discriminated union."""
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

    def test_extra_and_override_registries_mutually_exclusive(self):
        with pytest.raises(
            ValidationError,
            match="Only one of 'extraRegistries' or 'overrideRegistries' can be defined",
        ):
            ImageDevelopmentVersionFromDependency(
                dependency="positron",
                os=[_UBUNTU_24_OS],
                extraRegistries=[{"host": "ghcr.io", "namespace": "posit-dev"}],
                overrideRegistries=[{"host": "docker.io", "namespace": "posit"}],
            )

    def test_max_one_primary_os(self):
        with pytest.raises(
            ValidationError,
            match="Only one OS can be marked as primary",
        ):
            ImageDevelopmentVersionFromDependency(
                dependency="positron",
                os=[
                    {"name": "Ubuntu 24.04", "primary": True},
                    {"name": "Ubuntu 22.04", "primary": True},
                ],
            )


class TestVersionResolution:
    def test_prerelease_true_resolves_daily(self, patch_requests_get):
        """prerelease=True resolves to the daily build from the CDN."""
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            prerelease=True,
            os=[_UBUNTU_24_OS],
        )
        assert dev.get_version() == "2026.07.0-55"

    def test_prerelease_false_resolves_latest_stable(self, patch_requests_get):
        """prerelease=False resolves to the latest stable release."""
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            prerelease=False,
            os=[_UBUNTU_24_OS],
        )
        assert dev.get_version() == "2026.03.0-212"

    def test_prerelease_false_excludes_daily_version(self, patch_requests_get):
        """prerelease=False must not return the daily build version."""
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            prerelease=False,
            os=[_UBUNTU_24_OS],
        )
        assert dev.get_version() != "2026.07.0-55"


class TestUrlHandling:
    def test_get_url_by_os_returns_empty(self):
        """URL construction is delegated to the Containerfile template, not bakery."""
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            os=[_UBUNTU_24_OS],
        )
        assert dev.get_url_by_os() == {}
        assert dev.get_url_by_os(generalize_architecture=True) == {}

    def test_resolve_os_urls_returns_all_os(self, patch_requests_get):
        """_resolve_os_urls() returns all configured OSes without setting artifactDownloadURL."""
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            prerelease=True,
            os=[_UBUNTU_24_OS, _UBUNTU_22_OS],
        )
        resolved = dev._resolve_os_urls()
        assert len(resolved) == 2
        assert all(o.artifactDownloadURL is None for o in resolved)

    def test_resolve_os_urls_preserves_os_order(self, patch_requests_get):
        """OS entries survive _resolve_os_urls() with their names intact."""
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            prerelease=True,
            os=[_UBUNTU_24_OS, _UBUNTU_22_OS],
        )
        resolved = dev._resolve_os_urls()
        names = {o.name for o in resolved}
        assert names == {"Ubuntu 24.04", "Ubuntu 22.04"}


class TestOsHandling:
    def test_single_os_is_auto_primary(self, caplog):
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            os=[{"name": "Ubuntu 24.04"}],
        )
        assert dev.os[0].primary is True
        assert "WARNING" not in caplog.text

    def test_empty_os_logs_warning(self, caplog):
        ImageDevelopmentVersionFromDependency(dependency="positron", os=[])
        assert "No OSes defined for image development version" in caplog.text

    def test_no_primary_os_logs_warning(self, caplog):
        ImageDevelopmentVersionFromDependency(
            dependency="positron",
            os=[{"name": "Ubuntu 24.04"}, {"name": "Ubuntu 22.04"}],
        )
        assert "No OS marked as primary" in caplog.text

    def test_duplicate_os_deduplicated(self, caplog):
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            os=[_UBUNTU_24_OS, _UBUNTU_24_OS],
        )
        assert len(dev.os) == 1
        assert "Duplicate OS defined" in caplog.text

    def test_os_parent_set(self):
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            os=[_UBUNTU_24_OS],
        )
        assert dev.os[0].parent is dev


class TestRegistryHandling:
    def test_duplicate_registries_deduplicated(self, caplog):
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            os=[_UBUNTU_24_OS],
            extraRegistries=[
                {"host": "ghcr.io", "namespace": "posit-dev"},
                {"host": "ghcr.io", "namespace": "posit-dev"},
            ],
        )
        assert len(dev.extraRegistries) == 1
        assert "Duplicate registry defined" in caplog.text

    def test_all_registries_merges_with_parent(self):
        parent = _mock_parent()
        parent.all_registries = [
            BaseRegistry(host="docker.io", namespace="posit"),
            BaseRegistry(host="ghcr.io", namespace="posit-dev"),
        ]
        dev = ImageDevelopmentVersionFromDependency(
            parent=parent,
            dependency="positron",
            os=[_UBUNTU_24_OS],
            extraRegistries=[{"host": "ghcr.io", "namespace": "posit-preview"}],
        )
        hosts = {r.host for r in dev.all_registries}
        assert "docker.io" in hosts
        assert "ghcr.io" in hosts
        assert len(dev.all_registries) == 3

    def test_override_registries_replaces_parent(self):
        parent = _mock_parent()
        parent.all_registries = [BaseRegistry(host="docker.io", namespace="posit")]
        override = [BaseRegistry(host="ghcr.io", namespace="posit-preview")]
        dev = ImageDevelopmentVersionFromDependency(
            parent=parent,
            dependency="positron",
            os=[_UBUNTU_24_OS],
            overrideRegistries=override,
        )
        assert dev.all_registries == override


class TestAsImageVersion:
    def test_version_name(self, patch_requests_get):
        """as_image_version() produces an ImageVersion named after the resolved version."""
        dev = ImageDevelopmentVersionFromDependency(
            parent=_mock_parent(),
            dependency="positron",
            prerelease=True,
            os=[_UBUNTU_24_OS],
        )
        iv = dev.as_image_version()
        assert iv.name == "2026.07.0-55"

    def test_is_development_version(self, patch_requests_get):
        dev = ImageDevelopmentVersionFromDependency(
            parent=_mock_parent(),
            dependency="positron",
            prerelease=True,
            os=[_UBUNTU_24_OS],
        )
        iv = dev.as_image_version()
        assert iv.isDevelopmentVersion is True

    def test_values_passthrough(self, patch_requests_get):
        """values set on the dev version are present on the resulting ImageVersion."""
        dev = ImageDevelopmentVersionFromDependency(
            parent=_mock_parent(),
            dependency="positron",
            prerelease=True,
            os=[_UBUNTU_24_OS],
            values={"POSITRON_CHANNEL": "dailies"},
        )
        iv = dev.as_image_version()
        assert iv.values == {"POSITRON_CHANNEL": "dailies"}

    def test_no_release_channel_in_metadata(self, patch_requests_get):
        """dependency-sourced dev versions carry no release_channel metadata."""
        dev = ImageDevelopmentVersionFromDependency(
            parent=_mock_parent(),
            dependency="positron",
            prerelease=True,
            os=[_UBUNTU_24_OS],
        )
        iv = dev.as_image_version()
        assert "release_channel" not in iv.metadata

    def test_os_preserved(self, patch_requests_get):
        dev = ImageDevelopmentVersionFromDependency(
            parent=_mock_parent(),
            dependency="positron",
            prerelease=True,
            os=[_UBUNTU_24_OS, _UBUNTU_22_OS],
        )
        iv = dev.as_image_version()
        assert {o.name for o in iv.os} == {"Ubuntu 24.04", "Ubuntu 22.04"}

    def test_is_ephemeral(self, patch_requests_get):
        dev = ImageDevelopmentVersionFromDependency(
            parent=_mock_parent(),
            dependency="positron",
            prerelease=True,
            os=[_UBUNTU_24_OS],
        )
        iv = dev.as_image_version()
        assert iv.ephemeral is True

    def test_is_not_latest(self, patch_requests_get):
        dev = ImageDevelopmentVersionFromDependency(
            parent=_mock_parent(),
            dependency="positron",
            prerelease=True,
            os=[_UBUNTU_24_OS],
        )
        iv = dev.as_image_version()
        assert iv.latest is False


class TestRepr:
    def test_repr_contains_key_fields(self):
        dev = ImageDevelopmentVersionFromDependency(
            dependency="positron",
            prerelease=True,
            os=[_UBUNTU_24_OS],
        )
        r = repr(dev)
        assert 'sourceType="dependency"' in r
        assert "positron" in r
        assert "prerelease=True" in r
