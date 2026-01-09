import pytest
import python_on_whales

from posit_bakery.services import RegistryContainer

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


class TestRegistryContainer:
    @pytest.mark.slow
    def test_context_manager(self):
        python_on_whales.docker.image.pull("busybox:latest")
        with RegistryContainer() as registry:
            assert registry.status == "running"
            python_on_whales.docker.image.tag("busybox:latest", f"{registry.url}/busybox:latest")
            python_on_whales.docker.image.push(f"{registry.url}/busybox:latest")
            assert python_on_whales.docker.buildx.imagetools.inspect(f"{registry.url}/busybox:latest") is not None
        assert registry.status == "not_found"
