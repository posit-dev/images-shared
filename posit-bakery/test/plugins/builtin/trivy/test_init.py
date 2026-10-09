"""CLI-level tests for the `bakery trivy scan` command.

Phase 1 built structural-only tests against the `TrivyPlugin` stub; this phase
replaces them with CLI-level coverage now that `register_cli`/`execute`/`results`
have real bodies. Mirrors `test/plugins/builtin/wizcli/test_init.py`'s
zero-match-guard/platform-normalization/`--latest`/`--dev-spec` classes and adds
trivy-flag pass-through plus severity-breach-vs-general-error banner selection
coverage.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from posit_bakery.cli.main import app
from posit_bakery.plugins.builtin.trivy import TrivyPlugin
from posit_bakery.plugins.builtin.trivy.errors import (
    BakeryTrivyError,
    TRIVY_EXIT_CODE_GENERAL_ERROR,
    TRIVY_EXIT_CODE_SEVERITY_THRESHOLD,
)
from posit_bakery.plugins.builtin.trivy.options import TrivyOptions
from posit_bakery.plugins.protocol import BakeryToolPlugin, ToolCallResult

pytestmark = [
    pytest.mark.unit,
    pytest.mark.trivy,
]

runner = CliRunner()

BASIC_CONTEXT = str(Path(__file__).parent.parent.parent.parent / "resources" / "basic")


class TestTrivyPluginShell:
    """Structural guards carried over from Phase 1 -- still true once the stub bodies
    are replaced with real CLI/execute/results logic."""

    def test_name(self):
        assert TrivyPlugin.name == "trivy"

    def test_tool_options_class(self):
        assert TrivyPlugin.tool_options_class is TrivyOptions

    def test_isinstance_bakery_tool_plugin(self):
        assert isinstance(TrivyPlugin(), BakeryToolPlugin)


@pytest.fixture
def mocked_trivy_scan():
    """Mock BakeryConfig and TrivyPlugin.execute/results so the CLI can run
    end-to-end without needing trivy or built images."""
    with patch("posit_bakery.plugins.builtin.trivy.BakeryConfig") as mock_config:
        instance = MagicMock()
        instance.base_path = Path(BASIC_CONTEXT)
        # Non-empty so the zero-match guard does not abort the happy-path runs.
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
        assert "9999.99.99" in result.output
        mock_execute.assert_not_called()


class TestTrivyScanPlatformNormalization:
    """Regression coverage: `--image-platform linux/amd64` must not become
    `linux/linux/amd64`, and the resolved platform must reach the scan itself."""

    @pytest.mark.parametrize(
        "given,expected",
        [
            ("amd64", "linux/amd64"),
            ("arm64", "linux/arm64"),
            ("linux/amd64", "linux/amd64"),
            ("linux/arm64", "linux/arm64"),
        ],
    )
    def test_normalizes_platform(self, mocked_trivy_scan, given, expected):
        mock_config, mock_execute = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--context", BASIC_CONTEXT, "--image-platform", given],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mock_config.from_context.call_args[0][1]
        assert settings.filter.image_platform == [expected]
        # Filtering targets is not enough: the platform also selects which digest is
        # scanned.
        assert mock_execute.call_args.kwargs["platform"] == expected


class TestTrivyScanLatestFlag:
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


class TestTrivyScanDevSpec:
    """--dev-spec is accepted and parsed."""

    def test_dev_spec_accepted(self, mocked_trivy_scan):
        mock_config, _ = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--dev-spec", '{"version": "2026.05.0-dev+185-gSHA"}', "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mock_config.from_context.call_args[0][1]
        assert settings.dev_spec is not None
        assert settings.dev_spec.version == "2026.05.0-dev+185-gSHA"

    def test_dev_spec_invalid_json_rejected(self, mocked_trivy_scan):
        result = runner.invoke(
            app,
            ["trivy", "scan", "--dev-spec", "not-json", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code != 0

    def test_dev_spec_default_none(self, mocked_trivy_scan):
        mock_config, _ = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mock_config.from_context.call_args[0][1]
        assert settings.dev_spec is None


class TestTrivyScanFlagPassThrough:
    """Trivy-specific flags reach `execute()` in the shape `TrivyCommand`/`TrivySuite`
    expect: comma-separated strings split into lists, booleans/ints passed through
    as-is, and left unset (None) rather than a falsy default when the user does not
    pass them -- `TrivyCommand`'s CLI-vs-config precedence only overrides a
    bakery.yaml `tool_options` field when the CLI value is explicitly not None."""

    def test_severity_split_into_list(self, mocked_trivy_scan):
        _, mock_execute = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--severity", "CRITICAL,HIGH", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        assert mock_execute.call_args.kwargs["severity"] == ["CRITICAL", "HIGH"]

    def test_skip_files_split_into_list(self, mocked_trivy_scan):
        _, mock_execute = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--skip-files", "a,b", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        assert mock_execute.call_args.kwargs["skip_files"] == ["a", "b"]

    def test_skip_dirs_split_into_list(self, mocked_trivy_scan):
        _, mock_execute = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--skip-dirs", "/tmp,/var", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        assert mock_execute.call_args.kwargs["skip_dirs"] == ["/tmp", "/var"]

    def test_ignore_unfixed_flag(self, mocked_trivy_scan):
        _, mock_execute = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--ignore-unfixed", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        assert mock_execute.call_args.kwargs["ignore_unfixed"] is True

    def test_exit_code_flag(self, mocked_trivy_scan):
        _, mock_execute = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--exit-code", "2", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        assert mock_execute.call_args.kwargs["exit_code"] == 2

    def test_defaults_are_none(self, mocked_trivy_scan):
        _, mock_execute = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        assert mock_execute.call_args.kwargs["severity"] is None
        assert mock_execute.call_args.kwargs["skip_files"] is None
        assert mock_execute.call_args.kwargs["skip_dirs"] is None
        assert mock_execute.call_args.kwargs["ignore_unfixed"] is None
        assert mock_execute.call_args.kwargs["exit_code"] is None

    def test_scanners_split_into_list(self, mocked_trivy_scan):
        _, mock_execute = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--scanners", "vuln,secret", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        assert mock_execute.call_args.kwargs["scanners"] == ["vuln", "secret"]

    def test_timeout_passed_through_unsplit(self, mocked_trivy_scan):
        _, mock_execute = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--timeout", "5m0s", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        assert mock_execute.call_args.kwargs["timeout"] == "5m0s"

    def test_fail_on_severity_split_into_list(self, mocked_trivy_scan):
        _, mock_execute = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--fail-on-severity", "CRITICAL,HIGH", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        assert mock_execute.call_args.kwargs["failure_severity"] == ["CRITICAL", "HIGH"]

    def test_fail_on_severity_normalised(self, mocked_trivy_scan):
        _, mock_execute = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--fail-on-severity", "high, critical", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        assert mock_execute.call_args.kwargs["failure_severity"] == ["HIGH", "CRITICAL"]

    def test_fail_on_severity_rejects_unknown(self, mocked_trivy_scan):
        _, mock_execute = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--fail-on-severity", "HIGHH", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 2
        mock_execute.assert_not_called()

    def test_timeout_rejects_non_duration(self, mocked_trivy_scan):
        _, mock_execute = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--timeout", "soon", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 2
        mock_execute.assert_not_called()

    def test_new_flags_default_to_none(self, mocked_trivy_scan):
        _, mock_execute = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        assert mock_execute.call_args.kwargs["scanners"] is None
        assert mock_execute.call_args.kwargs["timeout"] is None
        assert mock_execute.call_args.kwargs["failure_severity"] is None


class TestTrivyScanHelp:
    def test_help_shows_trivy_panel_no_wizcli_or_auth_panel(self):
        result = runner.invoke(app, ["trivy", "scan", "--help"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "Trivy Options" in result.output
        assert "WizCLI Options" not in result.output
        assert "Authentication" not in result.output

    def test_trivy_app_has_no_tag_command(self):
        result = runner.invoke(app, ["trivy", "--help"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "tag" not in result.output
        assert "scan" in result.output


class TestTrivyPluginResultsBannerSelection:
    """`results()` raises non-zero on either a severity breach or a general error, and
    selects the matching banner -- mirrors `TrivySuite`'s own exit-code convention
    (`TRIVY_EXIT_CODE_SEVERITY_THRESHOLD` vs `TRIVY_EXIT_CODE_GENERAL_ERROR`)."""

    @staticmethod
    def _make_error_result(exit_code: int) -> ToolCallResult:
        target = MagicMock()
        err = BakeryTrivyError(
            message=f"trivy scan failed for {target}",
            tool_name="trivy",
            cmd=["trivy", "image"],
            exit_code=exit_code,
        )
        return ToolCallResult(
            exit_code=exit_code,
            tool_name="trivy",
            target=target,
            stdout="",
            stderr="",
            artifacts={"execution_error": err},
        )

    @staticmethod
    def _printed_text(mock_console) -> str:
        return " ".join(str(call.args[0]) for call in mock_console.print.call_args_list if call.args)

    def test_severity_breach_prints_breach_banner_and_exits_nonzero(self):
        plugin = TrivyPlugin()
        result = self._make_error_result(TRIVY_EXIT_CODE_SEVERITY_THRESHOLD)
        with patch("posit_bakery.plugins.builtin.trivy.stderr_console") as mock_console:
            with pytest.raises(typer.Exit) as exc_info:
                plugin.results([result])
        assert exc_info.value.exit_code == 1
        printed = self._printed_text(mock_console)
        assert "Severity threshold breach" in printed
        assert "failed to execute" not in printed

    def test_general_error_prints_error_banner_and_exits_nonzero(self):
        plugin = TrivyPlugin()
        result = self._make_error_result(TRIVY_EXIT_CODE_GENERAL_ERROR)
        with patch("posit_bakery.plugins.builtin.trivy.stderr_console") as mock_console:
            with pytest.raises(typer.Exit) as exc_info:
                plugin.results([result])
        assert exc_info.value.exit_code == 1
        printed = self._printed_text(mock_console)
        assert "failed to execute" in printed
        assert "Severity threshold breach" not in printed

    def test_no_errors_exits_zero(self):
        plugin = TrivyPlugin()
        target = MagicMock()
        result = ToolCallResult(exit_code=0, tool_name="trivy", target=target, stdout="", stderr="", artifacts=None)
        with patch("posit_bakery.plugins.builtin.trivy.stderr_console"):
            plugin.results([result])  # must not raise
