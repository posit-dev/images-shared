from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError, NameEmail

from posit_bakery.config.config import BakeryConfigDocument
from posit_bakery.config.repository import Repository

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


@pytest.mark.config
class TestRepository:
    def test_create_repository(self):
        """Test creating a generic ConfigRepository object does not raise an exception"""
        r = Repository(
            authors=[
                {"name": "author1", "email": "author1@posit.co"},
                {"name": "author2", "email": "author2@posit.co"},
            ],
            url="github.com/rstudio/example",
            vendor="Posit Software, PBC",
            maintainer={"name": "Posit Docker Team", "email": "docker@posit.co"},
        )

        assert str(r.url) == "https://github.com/rstudio/example"  # Tests URL https prepending
        assert len(r.authors) == 2
        assert NameEmail(name="author1", email="author1@posit.co") in r.authors
        assert NameEmail(name="author2", email="author2@posit.co") in r.authors
        assert r.vendor == "Posit Software, PBC"
        assert r.maintainer.name == "Posit Docker Team"
        assert r.maintainer.email == "docker@posit.co"

    def test_create_repository_url_only(self):
        """
        Test creating a generic ConfigRepository object with only the required arguments does not raise an exception
        and uses the expected default values for authors, vendor, and maintainer.
        """
        r = Repository(url="https://github.com/rstudio/example")
        assert str(r.url) == "https://github.com/rstudio/example"
        assert len(r.authors) == 0
        assert r.vendor == "Posit Software, PBC"
        assert r.maintainer.name == "Posit Docker Team"
        assert r.maintainer.email == "docker@posit.co"

    def test_create_repository_empty_validation_error(self):
        """Test that Repository requires at least a URL"""
        with pytest.raises(ValidationError):
            Repository()

    @pytest.mark.disable_patch_revision
    def test_revision_no_parent(self):
        """Test that revision returns None when no parent is set"""
        r = Repository(url="https://github.com/rstudio/example")
        assert r.revision is None

    @pytest.mark.disable_patch_revision
    def test_revision_with_parent_non_repo(self, tmpdir):
        """Test that revision returns None when parent is not a git repository"""
        parent = MagicMock(spec=BakeryConfigDocument)
        parent.path = tmpdir
        r = Repository(parent=parent, url="https://github.com/rstudio/example")
        assert r.revision is None

    @pytest.mark.disable_patch_revision
    def test_revision_with_parent_repo(self, tmpdir):
        """Test that revision returns the git commit SHA when parent is a git repository"""
        parent = MagicMock(spec=BakeryConfigDocument)
        parent.path = tmpdir
        with patch("git.Repo") as mock_repo:
            mock_repo.return_value.head.object.hexsha = "abc123"
            r = Repository(parent=parent, url="https://github.com/rstudio/example")
            assert r.revision == "abc123"
            mock_repo.assert_called_once_with(tmpdir, search_parent_directories=True)


class TestRepositoryAuthors:
    """Tests for repository author parsing and validation."""

    def test_authors_as_strings(self):
        """Test that authors can be provided as strings."""
        r = Repository(
            url="https://github.com/example/repo",
            authors=["Author One <author1@example.com>", "Author Two <author2@example.com>"],
        )
        assert len(r.authors) == 2

    def test_authors_as_dicts(self):
        """Test that authors can be provided as dictionaries."""
        r = Repository(
            url="https://github.com/example/repo",
            authors=[
                {"name": "Author One", "email": "author1@example.com"},
                {"name": "Author Two", "email": "author2@example.com"},
            ],
        )
        assert len(r.authors) == 2
        author_names = [a.name for a in r.authors]
        assert "Author One" in author_names
        assert "Author Two" in author_names

    def test_authors_mixed_strings_and_dicts(self):
        """Test that authors can be a mix of strings and dictionaries."""
        r = Repository(
            url="https://github.com/example/repo",
            authors=[
                "String Author <string@example.com>",
                {"name": "Dict Author", "email": "dict@example.com"},
            ],
        )
        assert len(r.authors) == 2

    def test_authors_invalid_type_raises(self):
        """Test that invalid author types raise ValidationError."""
        with pytest.raises(ValidationError, match="must be a string or dict"):
            Repository(
                url="https://github.com/example/repo",
                authors=[123],  # Invalid type
            )

    def test_authors_invalid_list_type_raises(self):
        """Test that a list with invalid types raises ValidationError."""
        with pytest.raises(ValidationError, match="must be a string or dict"):
            Repository(
                url="https://github.com/example/repo",
                authors=[None],  # Invalid type
            )

    def test_authors_dict_missing_email_raises(self):
        """Test that author dict without email raises ValidationError."""
        with pytest.raises(ValidationError, match="'email' must be provided"):
            Repository(
                url="https://github.com/example/repo",
                authors=[{"name": "No Email Author"}],
            )

    def test_authors_deduplicate(self, caplog):
        """Test that duplicate authors are deduplicated with a warning."""
        r = Repository(
            url="https://github.com/example/repo",
            authors=[
                {"name": "Same Author", "email": "same@example.com"},
                {"name": "Same Author", "email": "same@example.com"},
                {"name": "Same Author", "email": "same@example.com"},
            ],
        )
        assert len(r.authors) == 1
        assert "Duplicate authors found" in caplog.text
        assert "Same Author" in caplog.text

    def test_authors_sorted_alphabetically(self):
        """Test that authors are sorted alphabetically by string representation."""
        r = Repository(
            url="https://github.com/example/repo",
            authors=[
                {"name": "Zebra Author", "email": "zebra@example.com"},
                {"name": "Alpha Author", "email": "alpha@example.com"},
                {"name": "Middle Author", "email": "middle@example.com"},
            ],
        )
        assert len(r.authors) == 3
        # Should be sorted alphabetically
        author_names = [a.name for a in r.authors]
        assert author_names == ["Alpha Author", "Middle Author", "Zebra Author"]


class TestRepositoryMaintainer:
    """Tests for repository maintainer parsing and validation."""

    def test_maintainer_as_string(self):
        """Test that maintainer can be provided as a string."""
        r = Repository(
            url="https://github.com/example/repo",
            maintainer="Maintainer Name <maintainer@example.com>",
        )
        assert r.maintainer.name == "Maintainer Name"
        assert r.maintainer.email == "maintainer@example.com"

    def test_maintainer_as_dict(self):
        """Test that maintainer can be provided as a dictionary."""
        r = Repository(
            url="https://github.com/example/repo",
            maintainer={"name": "Dict Maintainer", "email": "dict@example.com"},
        )
        assert r.maintainer.name == "Dict Maintainer"
        assert r.maintainer.email == "dict@example.com"

    def test_maintainer_invalid_type_raises(self):
        """Test that invalid maintainer type raises ValidationError."""
        with pytest.raises(ValidationError, match="must be a string or dict"):
            Repository(
                url="https://github.com/example/repo",
                maintainer=12345,  # Invalid type
            )

    def test_maintainer_dict_missing_email_raises(self):
        """Test that maintainer dict without email raises ValidationError."""
        with pytest.raises(ValidationError, match="'email' must be provided"):
            Repository(
                url="https://github.com/example/repo",
                maintainer={"name": "No Email Maintainer"},
            )
