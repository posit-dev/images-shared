import pytest
from pydantic import ValidationError

from posit_bakery.models.image.tags import is_tag_valid


@pytest.mark.image
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
        assert is_tag_valid(tag)

    @pytest.mark.parametrize(
        "tag",
        [
            "a" * 129,
            "camelCase",
            "UPPERCASE",
            "with spaces",
            "-hyphen-first-char",
            "_underscore-first-char",
            ".period-first-char",
            "image:latest",
            "repo/image",
            "repo/image:tag",
            "2024.01.0+123.pro1",
        ],
    )
    def test_invalid_tags(self, tag: str):
        """Test invalid tags

        Ensures that tags match the expected format
        """
        assert not is_tag_valid(tag)

    @pytest.mark.parametrize(
        "tag",
        [
            "{{ build.os | condense }}-latest",
            "{{ build.version | tag_safe }}-{{ build.os | condense }}-min",
            "{{ build.version | clean_version }}-{{ build.os | condense }}-min",
            "tag-{{ build.os | condense }}",
        ],
    )
    def test_valid_tags_jinja(self, tag: str):
        """Test that tags including valid Jinja2

        Also ensures that tags match the expected format
        """
        assert is_tag_valid(tag)

    @pytest.mark.parametrize(
        "tag",
        [
            "{{ unclosed",
            "{ single | brace }",
            "{{ unmatching | braces }",
            "{{ valid }}-{{ invalid",
            "-test-{{ valid }}",
        ],
    )
    def test_invalid_tags_jinja(self, tag: str):
        """Test tags including invalid Jinja2

        Also ensures that tags match the expected format
        """
        assert not is_tag_valid(tag)
