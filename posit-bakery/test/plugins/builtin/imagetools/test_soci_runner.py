"""The SOCI command/workflow runner seam."""

from unittest.mock import MagicMock, patch

import pytest

from posit_bakery.error import BakeryToolRuntimeError
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.parallel import CommandResult
from posit_bakery.plugins.builtin.imagetools.options import SociOptions
from posit_bakery.plugins.builtin.imagetools.soci import SociConvert, SociConvertWorkflow

pytestmark = [pytest.mark.unit]


class StubRunner:
    def __init__(self, results):
        self.calls = []
        self._results = list(results)

    def run(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        return self._results.pop(0)


def _ok(cmd):
    return CommandResult(cmd=cmd, returncode=0, stdout=b"", stderr=b"", duration=0.0)


def _fail(cmd, stderr=b"not found"):
    return CommandResult(cmd=cmd, returncode=1, stdout=b"", stderr=stderr, duration=0.0)


def test_soci_command_routes_through_runner():
    cmd = SociConvert(soci_bin="soci", source="/tmp/src", destination="/tmp/out")
    runner = StubRunner([_ok(cmd.command)])
    result = cmd.run(runner=runner)
    assert runner.calls[0][0] == cmd.command
    assert result.returncode == 0


def test_soci_command_raises_on_runner_failure():
    cmd = SociConvert(soci_bin="soci", source="/tmp/src", destination="/tmp/out")
    runner = StubRunner([_fail(cmd.command, stderr=b"boom")])
    with pytest.raises(BakeryToolRuntimeError) as exc:
        cmd.run(runner=runner)
    assert exc.value.tool_name == "soci"


def _convert_workflow():
    target = MagicMock(spec=ImageTarget)
    target.image_name = "test-image"
    target.uid = "test-image-1-0-0"
    return SociConvertWorkflow(
        soci_bin="soci",
        oras_bin="oras",
        image_target=target,
        options=SociOptions(enabled=True),
        source_ref="ghcr.io/posit-dev/test-image/tmp:merged",
    )


def test_convert_workflow_threads_runner_through_all_three_steps():
    wf = _convert_workflow()
    runner = StubRunner([_ok(["oras", "cp"]), _ok(["soci", "convert"]), _ok(["oras", "cp"])])
    with patch.object(SociConvertWorkflow, "_read_converted_digest", return_value="sha256:abc123"):
        result = wf.run(runner=runner)

    assert result.success is True
    assert len(runner.calls) == 3
    assert runner.calls[0][0][:2] == ["oras", "cp"]  # pull (registry -> layout)
    assert "--standalone" in runner.calls[1][0]  # convert
    assert "--from-oci-layout" in runner.calls[2][0]  # push (layout -> registry)


def test_convert_workflow_failure_via_runner():
    wf = _convert_workflow()
    runner = StubRunner([_fail(["oras", "cp"], stderr=b"pull boom")])
    result = wf.run(runner=runner)
    assert result.success is False
    assert "pull boom" in (result.error or "")
