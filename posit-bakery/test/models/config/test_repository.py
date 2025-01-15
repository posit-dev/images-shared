import pytest

from posit_bakery.models.config.repository import ConfigRepository


@pytest.mark.config
@pytest.mark.schema
class TestConfigRepository:
    def test_create_config_repository(self):
        """Test creating a generic ConfigRepository object does not raise an exception"""
        ConfigRepository(
            authors=["author1", "author2"],
            url="github.com/rstudio/example",
            vendor="Posit Software, PBC",
            maintainer="docker@posit.co",
        )

    def test_create_config_repository_empty(self):
        """Test creating a generic ConfigRepository object with no arguments does not raise an exception

        Repository information is currently not expected to be required since it is used as labeling
        """
        ConfigRepository()
