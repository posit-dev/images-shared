import pytest

from posit_bakery.config.registry import Registry


pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


@pytest.mark.config
@pytest.mark.schema
class TestRegistry:
    def test_create_registry(self):
        """Test creating a generic ConfigRegistry object does not raise an exception"""
        Registry(host="docker.io", namespace="posit")

    def test_create_registry_no_namespace(self):
        """Test creating a generic ConfigRegistry object without a namespace does not raise an exception"""
        Registry(host="docker.io")

    def test_base_url(self):
        """Test the base_url property of a ConfigRegistry object"""
        c = Registry(host="docker.io", namespace="posit")
        assert c.base_url == "docker.io/posit"

    def test_base_url_no_namespace(self):
        """Test the base_url property of a ConfigRegistry object without a namespace"""
        c = Registry(host="docker.io")
        assert c.base_url == "docker.io"

    def test_hash(self):
        """Test the hash method of a ConfigRegistry object"""
        c1 = Registry(host="docker.io", namespace="posit")
        c2 = Registry(host="docker.io", namespace="posit")
        c3 = Registry(host="ghcr.io", namespace="posit")
        assert hash(c1) == hash(c2)
        assert hash(c1) != hash(c3)
