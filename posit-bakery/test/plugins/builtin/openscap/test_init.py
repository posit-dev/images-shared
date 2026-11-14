from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from posit_bakery.cli.main import app
from posit_bakery.plugins.builtin.openscap import OpenSCAPPlugin
from posit_bakery.plugins.builtin.openscap.errors import BakeryOpenSCAPError
from posit_bakery.plugins.builtin.openscap.options import FailOnEnum, OpenSCAPOptions, OutputFormatEnum
from posit_bakery.plugins.builtin.openscap.report import OpenSCAPScanNotRun
from posit_bakery.plugins.protocol import BakeryToolPlugin, ToolCallResult

pytestmark = [pytest.mark.unit, pytest.mark.openscap]

runner = CliRunner()
BASIC_CONTEXT = str(Path(__file__).parent.parent.parent.parent / "resources" / "basic")


def test_plugin_shell():
    assert OpenSCAPPlugin.name == "openscap"
    assert OpenSCAPPlugin.tool_options_class is OpenSCAPOptions
    assert isinstance(OpenSCAPPlugin(), BakeryToolPlugin)


@pytest.fixture
def mocked_scan():
    with patch("posit_bakery.plugins.builtin.openscap.BakeryConfig") as mock_config:
        instance = MagicMock()
        instance.base_path = Path(BASIC_CONTEXT)
        instance.targets = [MagicMock()]
        mock_config.from_context.return_value = instance
        with (
            patch.object(OpenSCAPPlugin, "execute", return_value=[]) as mock_execute,
            patch.object(OpenSCAPPlugin, "results"),
        ):
            yield mock_execute


def test_cli_passes_options(mocked_scan):
    result = runner.invoke(
        app,
        ["openscap", "scan", "--context", BASIC_CONTEXT, "--profile", "cis_level2_server", "--fail-on", "high",
         "--skip-rule", "a", "--skip-rule", "b", "--format", "json,markdown", "--image-platform", "arm64"],
        catch_exceptions=False,
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    kwargs = mocked_scan.call_args.kwargs
    assert kwargs["profile"] == "cis_level2_server"
    assert kwargs["fail_on"] == FailOnEnum.HIGH
    assert kwargs["skip_rules"] == ["a", "b"]
    assert kwargs["formats"] == [OutputFormatEnum.JSON, OutputFormatEnum.MARKDOWN]
    assert kwargs["platform"] == "linux/arm64"


def test_cli_unset_options_are_none(mocked_scan):
    result = runner.invoke(app, ["openscap", "scan", "--context", BASIC_CONTEXT], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    kwargs = mocked_scan.call_args.kwargs
    assert kwargs["profile"] is None and kwargs["fail_on"] is None and kwargs["formats"] is None


def test_cli_rejects_unknown_format(mocked_scan):
    result = runner.invoke(app, ["openscap", "scan", "--context", BASIC_CONTEXT, "--format", "pdf"])
    assert result.exit_code != 0
    mocked_scan.assert_not_called()


def _result(target, status, error=None):
    return ToolCallResult(
        exit_code=error.exit_code if error else 0,
        tool_name="openscap",
        target=target,
        stdout="",
        stderr="",
        artifacts={"report": OpenSCAPScanNotRun(status, "reason", status == "SKIPPED"), "status": status,
                   "execution_error": error},
    )  # fmt: skip


def test_results_skipped_passes(basic_standard_image_target):
    OpenSCAPPlugin().results([_result(basic_standard_image_target, "SKIPPED")])


def test_results_error_exits_nonzero(basic_standard_image_target):
    with pytest.raises(typer.Exit) as exc:
        OpenSCAPPlugin().results([_result(basic_standard_image_target, "ERROR", BakeryOpenSCAPError("boom"))])
    assert exc.value.exit_code == 1
