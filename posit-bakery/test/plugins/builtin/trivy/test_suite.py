import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from posit_bakery.image import ImageTarget
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

    def test_run_marks_error_on_missing_output_file(self, get_tmpconfig):
        """A zero exit code with no results file written is still treated as an error, not a silent success."""
        basic_tmpconfig = get_tmpconfig("basic")
        suite = TrivySuite(basic_tmpconfig.base_path, basic_tmpconfig.targets)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b""
        mock_result.stderr = b""

        with patch("posit_bakery.plugins.builtin.trivy.suite.subprocess.run", return_value=mock_result):
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

    @pytest.mark.slow
    @pytest.mark.skipif(shutil.which("trivy") is None, reason="trivy binary not installed")
    def test_run_integration(self, get_tmpconfig, monkeypatch):
        """Test running trivy against a real, small public image with the real trivy binary.

        Unlike hadolint (which only lints Containerfile text on disk), trivy needs a real,
        pullable image reference. The "basic" fixture's targets are template-rendered
        Containerfiles that are never built anywhere in the test suite, so `ImageTarget.ref()`
        would resolve to a local tag that was never built and `trivy image` would always fail
        to pull it. `ref()` is monkeypatched for a single target to point at a small,
        always-available public image instead. Everything else -- TrivyCommand construction,
        the real trivy subprocess invocation, and TrivyReport.load() SARIF parsing -- is
        exercised unmodified, against real output from a real trivy binary.
        """
        basic_tmpconfig = get_tmpconfig("basic")
        monkeypatch.setattr(ImageTarget, "ref", lambda self, *args, **kwargs: "alpine:3.19")

        target = basic_tmpconfig.targets[0]
        suite = TrivySuite(basic_tmpconfig.base_path, [target])
        report_collection, errors = suite.run()

        assert errors is None, f"real trivy scan failed: {errors}"
        assert target.image_name in report_collection
        assert target.uid in report_collection[target.image_name]
        _, report = report_collection[target.image_name][target.uid]

        results_file = suite.trivy_commands[0].results_file
        assert results_file.exists()
        raw = json.loads(results_file.read_text())
        sarif_run = raw["runs"][0]
        assert sarif_run["tool"]["driver"]["name"].lower() == "trivy"

        # The category must survive into real trivy output, not just the hand-written
        # fixture: upload-sarif reads it from here to give each file in a directory
        # upload its own code-scanning category.
        assert sarif_run["automationDetails"]["id"] == f"{suite.trivy_commands[0].scan_category}/"

        # Cross-check the parsed report against the real SARIF trivy wrote: every
        # counted severity bucket is non-negative, and they add up to exactly the
        # number of results trivy actually reported. This fails if TrivyReport.load()
        # mis-parses the real SARIF shape in a way the hand-written testdata fixture
        # (used by the mocked-subprocess unit tests above) wouldn't catch.
        assert report.critical_count >= 0
        assert report.high_count >= 0
        assert report.medium_count >= 0
        assert report.low_count >= 0
        assert report.unknown_count >= 0
        assert report.total_count == len(sarif_run["results"])
