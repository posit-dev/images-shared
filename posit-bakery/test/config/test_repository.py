import pytest
from pydantic import ValidationError, NameEmail

from posit_bakery.config.repository import Repository


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
