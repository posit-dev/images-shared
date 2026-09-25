import pytest

from test.helpers import select_targets_from_mocked_config


@pytest.fixture(autouse=True)
def _select_targets_from_mocked_config():
    """Plugin CLI tests mock BakeryConfig and set ``targets`` on it; route selection there."""
    with select_targets_from_mocked_config():
        yield
