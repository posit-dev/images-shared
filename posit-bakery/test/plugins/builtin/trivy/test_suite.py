from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from posit_bakery.plugins.builtin.trivy.suite import TrivySuite

pytestmark = [
    pytest.mark.unit,
    pytest.mark.trivy,
]

TRIVY_TESTDATA_DIR = (Path(__file__).parent / "testdata").absolute()


class TestTrivySuite:
    def test_init(self, get_config_obj):
        """Test that TrivySuite initializes with the correct attributes."""
        basic_config_obj = get_config_obj("basic")
        suite = TrivySuite(basic_config_obj.base_path, basic_config_obj.targets)
        assert suite.context == basic_config_obj.base_path
        assert len(suite.trivy_commands) == len(basic_config_obj.targets)

    def test_run_creates_results_directory(self, get_tmpconfig):
        """Test that run creates the results/trivy/ directory."""
        basic_tmpconfig = get_tmpconfig("basic")
        suite = TrivySuite(basic_tmpconfig.base_path, basic_tmpconfig.targets)

        sarif_bytes = (TRIVY_TESTDATA_DIR / "scan_result.sarif").read_bytes()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b""
        mock_result.stderr = b""

        def fake_run(cmd, **kwargs):
            output_path = Path(cmd[cmd.index("--output") + 1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(sarif_bytes)
            return mock_result

        with patch("posit_bakery.plugins.builtin.trivy.suite.subprocess.run", side_effect=fake_run):
            suite.run()

        results_dir = basic_tmpconfig.base_path / "results" / "trivy"
        assert results_dir.exists()

    def test_run_parses_sarif_results(self, get_tmpconfig):
        """Test that run parses SARIF results for each target."""
        basic_tmpconfig = get_tmpconfig("basic")
        suite = TrivySuite(basic_tmpconfig.base_path, basic_tmpconfig.targets)

        sarif_bytes = (TRIVY_TESTDATA_DIR / "scan_result.sarif").read_bytes()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b""
        mock_result.stderr = b""

        def fake_run(cmd, **kwargs):
            output_path = Path(cmd[cmd.index("--output") + 1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(sarif_bytes)
            return mock_result

        with patch("posit_bakery.plugins.builtin.trivy.suite.subprocess.run", side_effect=fake_run):
            report_collection, errors = suite.run()

        assert errors is None
        for target in basic_tmpconfig.targets:
            assert target.image_name in report_collection
            assert target.uid in report_collection[target.image_name]
            _, report = report_collection[target.image_name][target.uid]
            assert report.critical_count == 1
            assert report.total_count == 4

    def test_run_handles_execution_error(self, get_tmpconfig):
        """A non-zero trivy exit code is always a true execution error (no policy-violation exit code exists)."""
        basic_tmpconfig = get_tmpconfig("basic")
        suite = TrivySuite(basic_tmpconfig.base_path, basic_tmpconfig.targets)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = b"FATAL: unable to pull image"
        mock_result.stderr = b""

        with patch("posit_bakery.plugins.builtin.trivy.suite.subprocess.run", return_value=mock_result):
            report_collection, errors = suite.run()

        assert errors is not None

    def test_run_marks_error_on_unparseable_output(self, get_tmpconfig):
        """A zero exit code but garbled SARIF output is still treated as an error, not a clean pass."""
        basic_tmpconfig = get_tmpconfig("basic")
        suite = TrivySuite(basic_tmpconfig.base_path, basic_tmpconfig.targets)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b""
        mock_result.stderr = b""

        def fake_run(cmd, **kwargs):
            output_path = Path(cmd[cmd.index("--output") + 1])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("not valid json")
            return mock_result

        with patch("posit_bakery.plugins.builtin.trivy.suite.subprocess.run", side_effect=fake_run):
            report_collection, errors = suite.run()

        assert errors is not None

    def test_run_never_passes_exit_code_flag(self, get_tmpconfig):
        """Guards the Global Constraint: trivy's own --exit-code flag must never be set."""
        basic_tmpconfig = get_tmpconfig("basic")
        suite = TrivySuite(basic_tmpconfig.base_path, basic_tmpconfig.targets)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = b""
        mock_result.stderr = b""

        with patch("posit_bakery.plugins.builtin.trivy.suite.subprocess.run", return_value=mock_result) as mock_run:
            suite.run()

        for call in mock_run.call_args_list:
            cmd = call.args[0]
            assert "--exit-code" not in cmd

    def test_sequential_execution_one_call_per_target(self, get_tmpconfig):
        """Guards the Global Constraint: sequential, one subprocess.run per target, no parallel module."""
        basic_tmpconfig = get_tmpconfig("basic")
        suite = TrivySuite(basic_tmpconfig.base_path, basic_tmpconfig.targets)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = b""
        mock_result.stderr = b""

        with patch("posit_bakery.plugins.builtin.trivy.suite.subprocess.run", return_value=mock_result) as mock_run:
            suite.run()

        assert mock_run.call_count == len(basic_tmpconfig.targets)
