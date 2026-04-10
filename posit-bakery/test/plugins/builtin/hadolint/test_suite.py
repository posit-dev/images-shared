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

    def test_deduplicates_shared_containerfiles(self, get_tmpconfig):
        """Test that targets sharing the same Containerfile only run hadolint once."""
        basic_tmpconfig = get_tmpconfig("basic")
        suite = HadolintSuite(basic_tmpconfig.base_path, basic_tmpconfig.targets)

        # The basic fixture has 2 targets with different Containerfiles (std/min),
        # so hadolint should be called twice (once per unique Containerfile).
        hadolint_output = json.dumps([])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = hadolint_output.encode("utf-8")
        mock_result.stderr = b""

        with patch("posit_bakery.plugins.builtin.hadolint.suite.subprocess.run", return_value=mock_result) as mock_run:
            suite.run()

        assert mock_run.call_count == 2

    def test_deduplicates_matrix_targets(self, get_tmpconfig):
        """Test that matrix targets sharing a Containerfile are grouped and labeled 'matrix'."""
        basic_tmpconfig = get_tmpconfig("basic")
        targets = basic_tmpconfig.targets

        # Simulate matrix by duplicating a target (same containerfile, different uid)
        from copy import deepcopy
        extra_target = targets[0].model_copy(deep=True)
        extra_target.image_version = deepcopy(targets[0].image_version)
        extra_target.image_version.isMatrixVersion = True
        targets_with_matrix = [targets[0], extra_target, targets[1]]

        suite = HadolintSuite(basic_tmpconfig.base_path, targets_with_matrix)

        # The first two targets share a Containerfile, the third has a different one.
        groups = suite._group_commands_by_containerfile()
        assert len(groups) == 2

        first_containerfile = suite.hadolint_commands[0].containerfile_path
        assert len(groups[first_containerfile]) == 2

        # Run with mock and verify only 2 hadolint calls (not 3) and version_label is set
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b"[]"
        mock_result.stderr = b""

        with patch("posit_bakery.plugins.builtin.hadolint.suite.subprocess.run", return_value=mock_result) as mock_run:
            report_collection, errors = suite.run()

        assert mock_run.call_count == 2
        assert errors is None

        # The grouped entry should have version_label="matrix"
        for image_name, uid_reports in report_collection.items():
            for uid, (target, report) in uid_reports.items():
                if target.containerfile == targets[0].containerfile:
                    assert report.version_label == "matrix"
                else:
                    assert report.version_label is None

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
