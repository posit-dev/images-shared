"""Unit tests for the `bakery trivy scan` CLI command.

Guards the `--latest` filter pass-through and the zero-target guard. Mocks
BakeryConfig and the plugin's execute/results so the CLI can run end-to-end
without trivy installed or any built images.
"""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from posit_bakery.cli.main import app
from posit_bakery.plugins.builtin.trivy import TrivyPlugin
from posit_bakery.plugins.builtin.trivy.errors import BakeryTrivyError
from posit_bakery.plugins.builtin.trivy.options import TrivyOptions
from posit_bakery.plugins.builtin.trivy.report import TrivyReport, TrivyReportCollection
from posit_bakery.plugins.protocol import ToolCallResult

pytestmark = [
    pytest.mark.unit,
    pytest.mark.trivy,
]

runner = CliRunner()

BASIC_CONTEXT = str(Path(__file__).parent.parent.parent.parent / "resources" / "basic")


@pytest.fixture
def mocked_trivy_scan():
    """Mock BakeryConfig and TrivyPlugin.execute/results so the CLI can run
    end-to-end without needing trivy or built images."""
    with patch("posit_bakery.plugins.builtin.trivy.BakeryConfig") as mock_config:
        instance = MagicMock()
        instance.base_path = Path(BASIC_CONTEXT)
        instance.targets = [MagicMock()]
        mock_config.from_context.return_value = instance
        with (
            patch("posit_bakery.plugins.builtin.trivy.TrivyPlugin.execute") as mock_execute,
            patch("posit_bakery.plugins.builtin.trivy.TrivyPlugin.results"),
        ):
            mock_execute.return_value = []
            yield mock_config, mock_execute


class TestTrivyScanZeroMatchGuard:
    """A filter that matches no targets must fail loudly, not silently pass."""

    def test_no_targets_exits_nonzero(self):
        with patch("posit_bakery.plugins.builtin.trivy.BakeryConfig") as mock_config:
            instance = MagicMock()
            instance.base_path = Path(BASIC_CONTEXT)
            instance.targets = []
            mock_config.from_context.return_value = instance
            with patch("posit_bakery.plugins.builtin.trivy.TrivyPlugin.execute") as mock_execute:
                result = runner.invoke(
                    app,
                    ["trivy", "scan", "--context", BASIC_CONTEXT, "--image-version", "9999.99.99"],
                    catch_exceptions=False,
                )
        assert result.exit_code == 1
        assert "No image targets" in result.output
        mock_execute.assert_not_called()


class TestTrivyScanLatestFlag:
    """The --latest flag is passed through to settings."""

    def test_latest_passed_to_settings(self, mocked_trivy_scan):
        mock_config, _ = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--latest", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mock_config.from_context.call_args[0][1]
        assert settings.latest is True

    def test_latest_default_false(self, mocked_trivy_scan):
        mock_config, _ = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mock_config.from_context.call_args[0][1]
        assert settings.latest is False


class TestTrivyScanFlagPassthrough:
    def test_severity_and_fail_on_severity_passed_to_execute(self, mocked_trivy_scan):
        _, mock_execute = mocked_trivy_scan
        result = runner.invoke(
            app,
            [
                "trivy",
                "scan",
                "--context",
                BASIC_CONTEXT,
                "--severity",
                "HIGH,CRITICAL",
                "--fail-on-severity",
                "CRITICAL",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        _, kwargs = mock_execute.call_args
        assert kwargs["severity"] == "HIGH,CRITICAL"
        assert kwargs["fail_on_severity"] == "CRITICAL"

    def test_no_authentication_panel(self):
        """Guards the design decision: Trivy has no Authentication help panel."""
        result = runner.invoke(app, ["trivy", "scan", "--help"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "Authentication" not in result.output


class TestTrivyPluginExecute:
    """Direct unit tests for TrivyPlugin.execute(), bypassing the CLI/typer layer entirely.

    Mocks only TrivySuite, patched where __init__.py imports it
    (posit_bakery.plugins.builtin.trivy.TrivySuite), so the real fail-on-severity
    resolution/breach logic in execute() runs against real ImageTarget/TrivyReport/
    TrivyReportCollection/TrivyOptions instances.
    """

    @staticmethod
    @contextmanager
    def _mocked_suite(report_collection, errors, trivy_commands=None):
        """Patch TrivySuite (where __init__.py imports it) to return a fixed run() result."""
        with patch("posit_bakery.plugins.builtin.trivy.TrivySuite") as mock_suite_cls:
            mock_instance = MagicMock()
            mock_instance.run.return_value = (report_collection, errors)
            mock_instance.trivy_commands = trivy_commands or []
            mock_suite_cls.return_value = mock_instance
            yield

    def test_clean_scan_no_fail_on_severity_exits_zero(self, basic_standard_image_target):
        """No --fail-on-severity and no errors always exits 0, even with findings."""
        target = basic_standard_image_target
        report = TrivyReport(critical_count=1)
        report_collection = TrivyReportCollection()
        report_collection.add_report(target, report)

        with self._mocked_suite(report_collection, None):
            results = TrivyPlugin().execute(Path("/tmp"), [target], fail_on_severity=None)

        assert len(results) == 1
        result = results[0]
        assert result.exit_code == 0
        assert result.artifacts["report"] is report
        assert "severity_breach" not in result.artifacts

    def test_cli_fail_on_severity_breach_exits_one(self, basic_standard_image_target):
        """A CLI --fail-on-severity value matching a finding severity breaches."""
        target = basic_standard_image_target
        report = TrivyReport(critical_count=1)
        report_collection = TrivyReportCollection()
        report_collection.add_report(target, report)

        with self._mocked_suite(report_collection, None):
            results = TrivyPlugin().execute(Path("/tmp"), [target], fail_on_severity="CRITICAL")

        result = results[0]
        assert result.exit_code == 1
        assert result.artifacts["severity_breach"] is True

    def test_falls_back_to_target_tool_options_fail_on_severity(self, basic_standard_image_target):
        """No CLI --fail-on-severity falls back to the target's resolved TrivyOptions."""
        target = basic_standard_image_target
        report = TrivyReport(critical_count=1)
        report_collection = TrivyReportCollection()
        report_collection.add_report(target, report)

        mock_cmd = MagicMock()
        mock_cmd.image_target = target
        mock_cmd.tool_options = TrivyOptions(failOnSeverity=["CRITICAL"])

        with self._mocked_suite(report_collection, None, trivy_commands=[mock_cmd]):
            results = TrivyPlugin().execute(Path("/tmp"), [target], fail_on_severity=None)

        result = results[0]
        assert result.exit_code == 1
        assert result.artifacts["severity_breach"] is True

    def test_cli_fail_on_severity_wins_over_tool_options(self, basic_standard_image_target):
        """A CLI --fail-on-severity value fully replaces (not merges with) TrivyOptions."""
        target = basic_standard_image_target
        report = TrivyReport(low_count=1, critical_count=0)
        report_collection = TrivyReportCollection()
        report_collection.add_report(target, report)

        mock_cmd = MagicMock()
        mock_cmd.image_target = target
        mock_cmd.tool_options = TrivyOptions(failOnSeverity=["LOW"])

        with self._mocked_suite(report_collection, None, trivy_commands=[mock_cmd]):
            results = TrivyPlugin().execute(Path("/tmp"), [target], fail_on_severity="CRITICAL")

        result = results[0]
        assert result.exit_code == 0
        assert "severity_breach" not in result.artifacts

    def test_execution_error_for_target_exits_one(self, basic_standard_image_target):
        """A per-target execution error (matched by str(target) substring) exits non-zero."""
        target = basic_standard_image_target
        error = BakeryTrivyError(
            f"trivy scan failed for '{str(target)}'",
            "trivy",
            cmd=["trivy", "image", str(target)],
            exit_code=1,
        )

        with self._mocked_suite(TrivyReportCollection(), error):
            results = TrivyPlugin().execute(Path("/tmp"), [target])

        result = results[0]
        assert result.exit_code == 1
        assert result.artifacts["execution_error"] is error
        assert "report" not in result.artifacts


class TestTrivyPluginResults:
    """Direct unit tests for TrivyPlugin.results()."""

    def test_clean_results_does_not_raise(self, basic_standard_image_target):
        result = ToolCallResult(
            exit_code=0,
            tool_name="trivy",
            target=basic_standard_image_target,
            stdout="",
            stderr="",
            artifacts={"report": TrivyReport(critical_count=0)},
        )

        TrivyPlugin().results([result])  # must not raise

    def test_severity_breach_raises_exit(self, basic_standard_image_target):
        result = ToolCallResult(
            exit_code=1,
            tool_name="trivy",
            target=basic_standard_image_target,
            stdout="",
            stderr="",
            artifacts={"report": TrivyReport(critical_count=1), "severity_breach": True},
        )

        with pytest.raises(typer.Exit) as exc_info:
            TrivyPlugin().results([result])
        assert exc_info.value.exit_code == 1

    def test_execution_error_raises_exit(self, basic_standard_image_target):
        error = BakeryTrivyError("trivy scan failed", "trivy", cmd=["trivy"], exit_code=1)
        result = ToolCallResult(
            exit_code=1,
            tool_name="trivy",
            target=basic_standard_image_target,
            stdout="",
            stderr="",
            artifacts={"execution_error": error},
        )

        with pytest.raises(typer.Exit) as exc_info:
            TrivyPlugin().results([result])
        assert exc_info.value.exit_code == 1
