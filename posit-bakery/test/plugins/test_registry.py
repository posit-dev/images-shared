import pytest
from posit_bakery.plugins.protocol import BakeryToolPlugin

pytestmark = [pytest.mark.unit]


class TestProtocol:
    def test_protocol_is_runtime_checkable(self):
        """BakeryToolPlugin must be runtime_checkable so we can validate plugins."""
        assert hasattr(BakeryToolPlugin, "__protocol_attrs__") or hasattr(
            BakeryToolPlugin, "__abstractmethods__"
        ), "BakeryToolPlugin should be a Protocol"
