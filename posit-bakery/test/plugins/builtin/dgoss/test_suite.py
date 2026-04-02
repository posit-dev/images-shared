import json

import pytest

from posit_bakery.plugins.builtin.dgoss.suite import DGossSuite
from test.helpers import remove_images

pytestmark = [
    pytest.mark.unit,
    pytest.mark.goss,
]


class TestDGossSuite:
    def test_init(self, get_config_obj):
        """Test that DGossSuite initializes with the correct attributes."""
        basic_config_obj = get_config_obj("basic")
        dgoss_suite = DGossSuite(basic_config_obj.base_path, basic_config_obj.targets)
        assert dgoss_suite.context == basic_config_obj.base_path
        assert dgoss_suite.image_targets == basic_config_obj.targets
        assert len(dgoss_suite.dgoss_commands) == 2

    @pytest.mark.slow
    @pytest.mark.xdist_group(name="build")
    def test_run(self, get_tmpconfig):
        """Test that DGossSuite run executes the DGoss commands."""
        basic_tmpconfig = get_tmpconfig("basic")
        basic_tmpconfig.build_targets()

        dgoss_suite = DGossSuite(basic_tmpconfig.base_path, basic_tmpconfig.targets)

        report_collection, errors = dgoss_suite.run()

        assert errors is None
        assert len(report_collection.test_failures) == 0
        assert len(report_collection.get("test-image")) == 2
        for target in dgoss_suite.image_targets:
            results_file = target.context.base_path / "results" / "dgoss" / target.image_name / f"{target.uid}.json"
            assert results_file.exists()
            with open(results_file) as f:
                json.load(f)

        remove_images(basic_tmpconfig)
