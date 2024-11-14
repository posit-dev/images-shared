from posit_bakery.models import config


class TestConfigRegistry:
    def test_create_config_registry(self):
        """Test creating a generic ConfigRegistry object does not raise an exception"""
        config.ConfigRegistry(host="docker.io", namespace="posit")

    def test_create_config_registry_no_namespace(self):
        """Test creating a generic ConfigRegistry object without a namespace does not raise an exception"""
        config.ConfigRegistry(host="docker.io")

    def test_base_url(self):
        """Test the base_url property of a ConfigRegistry object"""
        c = config.ConfigRegistry(host="docker.io", namespace="posit")
        assert c.base_url == "docker.io/posit"

    def test_base_url_no_namespace(self):
        """Test the base_url property of a ConfigRegistry object without a namespace"""
        c = config.ConfigRegistry(host="docker.io")
        assert c.base_url == "docker.io"

    def test_hash(self):
        """Test the hash method of a ConfigRegistry object"""
        c1 = config.ConfigRegistry(host="docker.io", namespace="posit")
        c2 = config.ConfigRegistry(host="docker.io", namespace="posit")
        c3 = config.ConfigRegistry(host="ghcr.io", namespace="posit")
        assert hash(c1) == hash(c2)
        assert hash(c1) != hash(c3)


class TestConfigRepository:
    def test_create_config_repository(self):
        """Test creating a generic ConfigRepository object does not raise an exception"""
        config.ConfigRepository(
            authors=["author1", "author2"],
            url="github.com/rstudio/example",
            vendor="Posit Software, PBC",
            maintainer="docker@posit.co",
        )

    def test_create_config_repository_empty(self):
        """Test creating a generic ConfigRepository object with no arguments does not raise an exception

        Repository information is currently not expected to be required since it is used as labeling
        """
        config.ConfigRepository()


class TestConfig:
    def test_create_config(self, test_suite_basic_context, test_suite_basic_config_file):
        """Test creating a generic Config object does not raise an exception and test data appears as expected"""
        c = config.Config(
            filepath=test_suite_basic_config_file,
            context=test_suite_basic_context,
            document=config.GenericTOMLModel.load_toml_file_data(test_suite_basic_config_file),
            registry=[config.ConfigRegistry(host="docker.io", namespace="posit")],
            repository=config.ConfigRepository(
                authors={"author1", "author2"},
                url="github.com/rstudio/example",
                vendor="Posit Software, PBC",
                maintainer="docker@posit.co",
            )
        )
        assert c.authors == {"author1", "author2"}
        assert c.repository_url == "github.com/rstudio/example"
        assert c.vendor == "Posit Software, PBC"
        assert c.maintainer == "docker@posit.co"
        assert c.registry_urls == ["docker.io/posit"]
        assert c.get_commit_sha() == ""

    def test_load_file(self, test_suite_basic_config_file):
        """Test that the load_file method returns a Config object with expected data"""
        c = config.Config.load_file(test_suite_basic_config_file)
        assert c.authors == {"Author 1 <author1@posit.co>", "Author 2 <author2@posit.co>"}
        assert c.repository_url == "github.com/rstudio/posit-images-shared"
        assert c.vendor == "Posit Software, PBC"
        assert c.maintainer == "docker@posit.co"
        assert len(c.registry) == 2
        assert c.registry_urls == ["docker.io/posit", "ghcr.io/posit-dev"]

    def test_merge(self, test_suite_basic_context, test_suite_basic_config_file, test_suite_basic_config_obj):
        """Test that the merge method updates the Config object with the provided Config object"""
        # Test existing values
        assert test_suite_basic_config_obj.authors == {"Author 1 <author1@posit.co>", "Author 2 <author2@posit.co>"}
        assert test_suite_basic_config_obj.repository_url == "github.com/rstudio/posit-images-shared"
        assert test_suite_basic_config_obj.vendor == "Posit Software, PBC"
        assert test_suite_basic_config_obj.maintainer == "docker@posit.co"
        assert len(test_suite_basic_config_obj.registry) == 2
        assert test_suite_basic_config_obj.registry_urls == ["docker.io/posit", "ghcr.io/posit-dev"]

        # Test overriding values without modifying registry
        c_override = config.Config(
            filepath=test_suite_basic_config_file,
            context=test_suite_basic_context,
            document=config.GenericTOMLModel.load_toml_file_data(test_suite_basic_config_file),
            registry=[],
            repository=config.ConfigRepository(
                authors={"Author 3 <author3@posit.co", "Author 4 <author4@posit.co>"},
                url="github.com/rstudio/example",
                vendor="Example Company",
                maintainer="images@example.com",
            )
        )
        test_suite_basic_config_obj.merge(c_override)
        assert test_suite_basic_config_obj.authors == {"Author 3 <author3@posit.co", "Author 4 <author4@posit.co>"}
        assert test_suite_basic_config_obj.repository_url == "github.com/rstudio/example"
        assert test_suite_basic_config_obj.vendor == "Example Company"
        assert test_suite_basic_config_obj.maintainer == "images@example.com"
        assert len(test_suite_basic_config_obj.registry) == 2
        assert test_suite_basic_config_obj.registry_urls == ["docker.io/posit", "ghcr.io/posit-dev"]

        # Test overriding registry
        c_override.registry = [config.ConfigRegistry(host="docker.io", namespace="example")]
        test_suite_basic_config_obj.merge(c_override)
        assert len(test_suite_basic_config_obj.registry) == 1
        assert test_suite_basic_config_obj.registry_urls == ["docker.io/example"]
