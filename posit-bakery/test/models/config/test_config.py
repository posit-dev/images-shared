import pytest
import tomlkit

from posit_bakery.models import Config
from posit_bakery.models.generic import GenericTOMLModel
from posit_bakery.models.config.document import ConfigDocument
from posit_bakery.models.config.registry import ConfigRegistry
from posit_bakery.models.config.repository import ConfigRepository

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


class TestConfigLoad:
    pass


class TestConfig:
    def test_create_config(self, basic_context, basic_config_file):
        """Test creating a generic Config object does not raise an exception and test data appears as expected"""
        doc: tomlkit.TOMLDocument = GenericTOMLModel.read(basic_config_file)
        c = Config(
            filepath=basic_config_file, context=basic_context, document=doc, model=ConfigDocument(**doc.unwrap())
        )
        assert c.authors == [
            "Author 1 <author1@posit.co>",
            "Author 2 <author2@posit.co>",
        ]
        assert c.repository_url == "github.com/posit-dev/images-shared"
        assert c.vendor == "Posit Software, PBC"
        assert c.maintainer == "docker@posit.co"
        assert "docker.io/posit" in c.registry_urls
        assert c.get_commit_sha() == ""

    def test_load_file(self, basic_config_file):
        """Test that the load_file method returns a Config object with expected data"""
        c = Config.load(basic_config_file)
        assert c.authors == ["Author 1 <author1@posit.co>", "Author 2 <author2@posit.co>"]
        assert c.repository_url == "github.com/posit-dev/images-shared"
        assert c.vendor == "Posit Software, PBC"
        assert c.maintainer == "docker@posit.co"
        assert len(c.registries) == 2
        assert "docker.io/posit" in c.registry_urls
        assert "ghcr.io/posit-dev" in c.registry_urls

    @pytest.mark.skip(reason="TODO: Handle overrides not specifying all fields")
    def test_update(self, basic_context, basic_config_file, basic_config_obj):
        """Test that the update method updates the Config object with the provided Config object"""
        # Test existing values
        assert basic_config_obj.authors == ["Author 1 <author1@posit.co>", "Author 2 <author2@posit.co>"]
        assert basic_config_obj.repository_url == "github.com/posit-dev/images-shared"
        assert basic_config_obj.vendor == "Posit Software, PBC"
        assert basic_config_obj.maintainer == "docker@posit.co"
        assert len(basic_config_obj.registries) == 2
        assert "docker.io/posit" in basic_config_obj.registry_urls
        assert "ghcr.io/posit-dev" in basic_config_obj.registry_urls

        # Test overriding values without modifying registry
        c_override = Config(
            filepath=basic_config_file,
            context=basic_context,
            document=GenericTOMLModel.read(basic_config_file),
            registries=[],
            repository=ConfigRepository(
                authors=["Author 3 <author3@posit.co", "Author 4 <author4@posit.co>"],
                url="github.com/rstudio/example",
                vendor="Example Company",
                maintainer="images@example.com",
            ),
        )
        basic_config_obj.update(c_override)
        assert basic_config_obj.authors == ["Author 3 <author3@posit.co", "Author 4 <author4@posit.co>"]
        assert basic_config_obj.repository_url == "github.com/rstudio/example"
        assert basic_config_obj.vendor == "Example Company"
        assert basic_config_obj.maintainer == "images@example.com"
        assert len(basic_config_obj.registries) == 2
        assert "docker.io/posit" in basic_config_obj.registry_urls
        assert "ghcr.io/posit-dev" in basic_config_obj.registry_urls

        # Test overriding registry
        c_override.registries = [ConfigRegistry(host="docker.io", namespace="example")]
        basic_config_obj.update(c_override)
        assert len(basic_config_obj.registries) == 1
        assert "docker.io/example" in basic_config_obj.registry_urls
