import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from posit_bakery.plugins.builtin.hadolint.suite import HadolintSuite
from posit_bakery.plugins.builtin.hadolint.options import HadolintOptions

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hadolint,
]


class TestHadolintSuite:
    def test_init(self, get_config_obj):
        """Test that HadolintSuite initializes with the correct attributes."""
        basic_config_obj = get_config_obj("basic")
        suite = HadolintSuite(basic_config_obj.base_path, basic_config_obj.targets)
        assert suite.context == basic_config_obj.base_path
        assert suite.image_targets == basic_config_obj.targets
        assert len(suite.hadolint_commands) == 2

    def test_run_creates_results_directory(self, get_tmpconfig):
        """Test that run creates the results/hadolint/ directory."""
        basic_tmpconfig = get_tmpconfig("basic")
        suite = HadolintSuite(basic_tmpconfig.base_path, basic_tmpconfig.targets)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"[]"
        mock_result.stderr = b""

        with patch("posit_bakery.plugins.builtin.hadolint.suite.subprocess.run", return_value=mock_result):
            suite.run()

        results_dir = basic_tmpconfig.base_path / "results" / "hadolint"
        assert results_dir.exists()

    def test_run_writes_json_results(self, get_tmpconfig):
        """Test that run writes JSON results for each target."""
        basic_tmpconfig = get_tmpconfig("basic")
        suite = HadolintSuite(basic_tmpconfig.base_path, basic_tmpconfig.targets)

        hadolint_output = json.dumps([
            {"code": "DL3008", "column": 1, "file": "Containerfile", "level": "warning",
             "line": 10, "message": "Pin versions"}
        ])
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = hadolint_output.encode("utf-8")
        mock_result.stderr = b""

        with patch("posit_bakery.plugins.builtin.hadolint.suite.subprocess.run", return_value=mock_result):
            report_collection, errors = suite.run()

        assert errors is None
        for target in basic_tmpconfig.targets:
            results_file = (
                basic_tmpconfig.base_path / "results" / "hadolint" / target.image_name / f"{target.uid}.json"
            )
            assert results_file.exists()
            with open(results_file) as f:
                data = json.load(f)
            assert len(data) == 1
            assert data[0]["code"] == "DL3008"

    def test_run_parses_empty_results(self, get_tmpconfig):
        """Test that run handles empty hadolint output (no issues)."""
        basic_tmpconfig = get_tmpconfig("basic")
        suite = HadolintSuite(basic_tmpconfig.base_path, basic_tmpconfig.targets)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"[]"
        mock_result.stderr = b""

        with patch("posit_bakery.plugins.builtin.hadolint.suite.subprocess.run", return_value=mock_result):
            report_collection, errors = suite.run()

        assert errors is None
        for image_name, targets in report_collection.items():
            for uid, (_, report) in targets.items():
                assert report.total_count == 0

    def test_run_handles_parse_error(self, get_tmpconfig):
        """Test that run creates an error when JSON parsing fails and exit code is non-zero."""
        basic_tmpconfig = get_tmpconfig("basic")
        suite = HadolintSuite(basic_tmpconfig.base_path, basic_tmpconfig.targets)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = b"not valid json"
        mock_result.stderr = b"hadolint: error"

        with patch("posit_bakery.plugins.builtin.hadolint.suite.subprocess.run", return_value=mock_result):
            report_collection, errors = suite.run()

        assert errors is not None

    @pytest.mark.slow
    def test_run_integration(self, get_tmpconfig):
        """Test running hadolint against real Containerfiles."""
        basic_tmpconfig = get_tmpconfig("basic")
        suite = HadolintSuite(basic_tmpconfig.base_path, basic_tmpconfig.targets)
        report_collection, errors = suite.run()

        assert errors is None
        assert len(report_collection) > 0
        for target in basic_tmpconfig.targets:
            results_file = (
                basic_tmpconfig.base_path / "results" / "hadolint" / target.image_name / f"{target.uid}.json"
            )
            assert results_file.exists()
