import pytest


@pytest.fixture(autouse=True)
def _clear_github_env(monkeypatch):
    """Drop the runner's GITHUB_ACTIONS and GITHUB_TOKEN so the dgoss command's
    GH_TOKEN forwarding does not leak into tests that assert exact env/cmd
    contents. Tests that exercise the forwarding behaviour set them explicitly."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
