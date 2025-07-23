import pytest

from posit_bakery.config.repository import Repository


@pytest.mark.config
@pytest.mark.schema
class TestConfigRepository:
    def test_create_config_repository(self):
        """Test creating a generic ConfigRepository object does not raise an exception"""
        Repository(
            **{
                "authors": [
                    {"name": "author1", "email": "author1@posit.co"},
                    {"name": "author2", "email": "author2@posit.co"},
                ],
                "url": "github.com/rstudio/example",
                "vendor": "Posit Software, PBC",
                "maintainer": {"name": "Posit Docker Team", "email": "docker@posit.co"},
            }
        )

    def test_create_config_repository_url_only(self):
        """Test creating a generic ConfigRepository object with only the required arguments does not raise an exception"""
        Repository(url="https://github.com/rstudio/example")
