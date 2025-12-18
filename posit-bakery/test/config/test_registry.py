import pytest
from pydantic import ValidationError

from posit_bakery.config.registry import BaseRegistry, Registry

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


class TestRegistry:
    def test_create_registry(self):
        """Test creating a generic ConfigRegistry object does not raise an exception"""
        BaseRegistry(host="docker.io", namespace="posit")

    def test_create_registry_no_namespace(self):
        """Test creating a generic ConfigRegistry object without a namespace does not raise an exception"""
        BaseRegistry(host="docker.io")

    def test_base_url(self):
        """Test the base_url property of a ConfigRegistry object"""
        c = BaseRegistry(host="docker.io", namespace="posit")
        assert c.base_url == "docker.io/posit"

    def test_base_url_no_namespace(self):
        """Test the base_url property of a ConfigRegistry object without a namespace"""
        c = BaseRegistry(host="docker.io")
        assert c.base_url == "docker.io"

    def test_hash(self):
        """Test the hash method of a ConfigRegistry object"""
        c1 = BaseRegistry(host="docker.io", namespace="posit")
        c2 = BaseRegistry(host="docker.io", namespace="posit")
        c3 = BaseRegistry(host="ghcr.io", namespace="posit")
        assert hash(c1) == hash(c2)
        assert hash(c1) != hash(c3)


class TestRegistryImage:
    def test_create_registry_with_name(self):
        """Test that BaseRegistry does not accept a name parameter."""
        with pytest.raises(ValidationError):
            BaseRegistry(
                host="docker.io",
                namespace="posit",
                name="connect",
            )

    def test_create_registry_with_repository(self):
        """Test creating a Registry object with a repository field."""
        r = Registry(host="docker.io", namespace="posit", repository="connect")
        assert r.host == "docker.io"
        assert r.namespace == "posit"
        assert r.repository == "connect"

    def test_registry_base_url_with_repository(self):
        """Test the base_url property of a Registry object with repository."""
        r = Registry(host="docker.io", namespace="posit", repository="connect")
        assert r.base_url == "docker.io/posit"
