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
@pytest.mark.schema
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
