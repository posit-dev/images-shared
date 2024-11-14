from posit_bakery.models import config


class TestConfigRegistry:
    def test_create_config_registry(self):
        config.ConfigRegistry(host="docker.io", namespace="posit")

    def test_create_config_registry_no_namespace(self):
        config.ConfigRegistry(host="docker.io")

    def test_base_url(self):
        c = config.ConfigRegistry(host="docker.io", namespace="posit")
        assert c.base_url == "docker.io/posit"

    def test_base_url_no_namespace(self):
        c = config.ConfigRegistry(host="docker.io")
        assert c.base_url == "docker.io"

    def test_hash(self):
        c1 = config.ConfigRegistry(host="docker.io", namespace="posit")
        c2 = config.ConfigRegistry(host="docker.io", namespace="posit")
        c3 = config.ConfigRegistry(host="ghcr.io", namespace="posit")
        assert hash(c1) == hash(c2)
        assert hash(c1) != hash(c3)


class TestConfigRepository:
    def test_create_config_repository(self):
        config.ConfigRepository(
            authors=["author1", "author2"],
            url="github.com/rstudio/example",
            vendor="Posit Software, PBC",
            maintainer="docker@posit.co",
        )

    def test_create_config_repository_empty(self):
        config.ConfigRepository()


class TestConfig:
    def test_create_config(self, test_suite_basic_context, test_suite_basic_config_file):
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
        c = config.Config.load_file(test_suite_basic_config_file)
        assert c.authors == {"Author 1 <author1@posit.co>", "Author 2 <author2@posit.co>"}
        assert c.repository_url == "github.com/rstudio/posit-images-shared"
        assert c.vendor == "Posit Software, PBC"
        assert c.maintainer == "docker@posit.co"
        assert len(c.registry) == 2
        assert c.registry_urls == ["docker.io/posit", "ghcr.io/posit-dev"]

    def test_merge(self, test_suite_basic_context, test_suite_basic_config_file):
        c = config.Config.load_file(test_suite_basic_config_file)
        assert c.authors == {"Author 1 <author1@posit.co>", "Author 2 <author2@posit.co>"}
        assert c.repository_url == "github.com/rstudio/posit-images-shared"
        assert c.vendor == "Posit Software, PBC"
        assert c.maintainer == "docker@posit.co"
        assert len(c.registry) == 2
        assert c.registry_urls == ["docker.io/posit", "ghcr.io/posit-dev"]

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
        c.merge(c_override)
        assert c.authors == {"Author 3 <author3@posit.co", "Author 4 <author4@posit.co>"}
        assert c.repository_url == "github.com/rstudio/example"
        assert c.vendor == "Example Company"
        assert c.maintainer == "images@example.com"
        assert len(c.registry) == 2
        assert c.registry_urls == ["docker.io/posit", "ghcr.io/posit-dev"]

        c_override.registry = [config.ConfigRegistry(host="docker.io", namespace="example")]
        c.merge(c_override)
        assert len(c.registry) == 1
        assert c.registry_urls == ["docker.io/example"]
