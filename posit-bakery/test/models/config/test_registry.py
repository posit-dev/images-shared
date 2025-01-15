import pytest

from posit_bakery.models.config.registry import ConfigRegistry


@pytest.mark.config
@pytest.mark.schema
class TestConfigRegistry:
    def test_create_config_registry(self):
        """Test creating a generic ConfigRegistry object does not raise an exception"""
        ConfigRegistry(host="docker.io", namespace="posit")

    def test_create_config_registry_no_namespace(self):
        """Test creating a generic ConfigRegistry object without a namespace does not raise an exception"""
        ConfigRegistry(host="docker.io")

    def test_base_url(self):
        """Test the base_url property of a ConfigRegistry object"""
        c = ConfigRegistry(host="docker.io", namespace="posit")
        assert c.base_url == "docker.io/posit"

    def test_base_url_no_namespace(self):
        """Test the base_url property of a ConfigRegistry object without a namespace"""
        c = ConfigRegistry(host="docker.io")
        assert c.base_url == "docker.io"

    def test_hash(self):
        """Test the hash method of a ConfigRegistry object"""
        c1 = ConfigRegistry(host="docker.io", namespace="posit")
        c2 = ConfigRegistry(host="docker.io", namespace="posit")
        c3 = ConfigRegistry(host="ghcr.io", namespace="posit")
        assert hash(c1) == hash(c2)
        assert hash(c1) != hash(c3)
