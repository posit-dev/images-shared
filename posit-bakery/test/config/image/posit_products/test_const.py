import importlib

import pytest

import posit_bakery.config.image.posit_product.const as product_const

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
    pytest.mark.product_version,
]


class TestWorkbenchDailyUrl:
    """WORKBENCH_DAILY_URL contains a {release_branch} template slot."""

    def test_contains_release_branch_placeholder(self):
        assert "{release_branch}" in product_const.WORKBENCH_DAILY_URL

    def test_formats_with_latest(self):
        url = product_const.WORKBENCH_DAILY_URL.format(release_branch="latest")
        assert url == "https://dailies.rstudio.com/rstudio/latest/index.json"

    def test_formats_with_named_branch(self):
        url = product_const.WORKBENCH_DAILY_URL.format(release_branch="apple-blossom")
        assert url == "https://dailies.rstudio.com/rstudio/apple-blossom/index.json"

    def test_formats_with_calver_branch(self):
        url = product_const.WORKBENCH_DAILY_URL.format(release_branch="2026.07")
        assert url == "https://dailies.rstudio.com/rstudio/2026.07/index.json"
