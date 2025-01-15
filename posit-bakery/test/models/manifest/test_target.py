import pytest
from pydantic import ValidationError

from posit_bakery.models.manifest.target import ManifestTarget


@pytest.mark.manifest
@pytest.mark.schema
class TestManifestTarget:
    @pytest.mark.parametrize(
        "tag",
        [
            "a" * 128,
            "latest",
            "latest-min",
            "latest-std",
            "v1",
            "v1.0",
            "v1.2.3",
            "2025.01.0",
            "2025.01.0-21",
            "2024.01.0-123.pro1",
            "ubuntu-24.04",
            "ubuntu2404",
            "ubuntu-24.04_801186b",
            "ubuntu-24.04-min",
        ],
    )
    def test_valid_tags(self, tag: str):
        """Test valid tags do not fail validation

        Ensures that tags match the expected format
        """
        ManifestTarget(tags=[tag])
        ManifestTarget(latest_tags=[tag])

    @pytest.mark.parametrize(
        "tag",
        [
            "a" * 129,
            "camelCase",
            "UPPERCASE",
            "with spaces",
            "image:latest",
            "repo/image",
            "repo/image:tag",
            "2024.01.0+123.pro1",
        ],
    )
    def test_invalid_tags(self, tag: str):
        """Test invalid tags raise a ValidationError

        Ensures that tags match the expected format
        """
        with pytest.raises(ValidationError):
            ManifestTarget(tags=[tag])

        with pytest.raises(ValidationError):
            ManifestTarget(latest_tags=[tag])

    @pytest.mark.parametrize(
        "tag",
        [
            "{{ build.os | condense }}-latest",
            "{{ build.version | tag_safe }}-{{ build.os | condense }}-min",
            "{{ build.version | clean_version }}-{{ build.os | condense }}-min",
        ],
    )
    def test_valid_tags_jinja(self, tag: str):
        """Test that tags including valid Jinja2 do not fail validation

        Also ensures that tags match the expected format
        """

        ManifestTarget(tags=[tag])
        ManifestTarget(latest_tags=[tag])

    @pytest.mark.parametrize(
        "tag",
        [
            "{{ unclosed",
            "{ single | brace }",
            "{{ unmatching | braces }",
            "{{ valid }}-{{ invalid",
        ],
    )
    def test_invalid_tags_jinja(self, tag: str):
        """Test that tags including invalid Jinja2 fail validation

        Also ensures that tags match the expected format
        """
        with pytest.raises(ValidationError):
            ManifestTarget(tags=[tag])

        with pytest.raises(ValidationError):
            ManifestTarget(latest_tags=[tag])
