import importlib

import pytest

import posit_bakery.config.image.posit_product.const as product_const

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
    pytest.mark.product_version,
]


class TestWorkbenchDailyUrl:
    """Test that WORKBENCH_DAILY_URL is constructed from the BAKERY_WORKBENCH_RELEASE_BRANCH env var."""

    def test_default_url(self, monkeypatch):
        """When BAKERY_WORKBENCH_RELEASE_BRANCH is not set, the URL defaults to 'latest'."""
        monkeypatch.delenv("BAKERY_WORKBENCH_RELEASE_BRANCH", raising=False)
        importlib.reload(product_const)

        assert product_const.WORKBENCH_DAILY_URL == "https://dailies.rstudio.com/rstudio/latest/index.json"

    @pytest.mark.parametrize(
        "branch",
        [
            pytest.param("globemaster-allium", id="globemaster-allium"),
            pytest.param("apple-blossom", id="apple-blossom"),
        ],
    )
    def test_custom_release_branch(self, monkeypatch, branch):
        """When BAKERY_WORKBENCH_RELEASE_BRANCH is set, the URL uses the branch name."""
        monkeypatch.setenv("BAKERY_WORKBENCH_RELEASE_BRANCH", branch)
        importlib.reload(product_const)

        assert product_const.WORKBENCH_DAILY_URL == f"https://dailies.rstudio.com/rstudio/{branch}/index.json"

    def test_empty_string_uses_empty_path(self, monkeypatch):
        """When BAKERY_WORKBENCH_RELEASE_BRANCH is set to an empty string, the empty value is used."""
        monkeypatch.setenv("BAKERY_WORKBENCH_RELEASE_BRANCH", "")
        importlib.reload(product_const)

        assert product_const.WORKBENCH_DAILY_URL == "https://dailies.rstudio.com/rstudio//index.json"
