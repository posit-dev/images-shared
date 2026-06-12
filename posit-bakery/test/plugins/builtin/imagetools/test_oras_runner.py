"""The ORAS command/workflow runner seam: when a CommandRunner is supplied, commands
execute through it (gaining tracked-spawn + retry) instead of calling subprocess directly."""

from unittest.mock import MagicMock

import pytest

from posit_bakery.error import BakeryToolRuntimeError
from posit_bakery.image.image_target import ImageTarget, StringableList
from posit_bakery.parallel import CommandResult
from posit_bakery.plugins.builtin.imagetools.oras import (
    OrasIndexCopyWorkflow,
    OrasIndexCreateWorkflow,
    OrasIndexVerifyWorkflow,
    OrasManifestIndexCreate,
)

pytestmark = [pytest.mark.unit]


class StubRunner:
    """Records commands and returns preset CommandResults (a CommandRunner seam stand-in)."""

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


@pytest.fixture
def mock_image_target_factory():
    def _make():
        t = MagicMock(spec=ImageTarget)
        t.image_name = "test-image"
        t.uid = "test-image-1-0-0"
        t.temp_registry = "ghcr.io/posit-dev"
        t.get_merge_sources.return_value = [
            "ghcr.io/posit-dev/test/tmp@sha256:amd64digest",
            "ghcr.io/posit-dev/test/tmp@sha256:arm64digest",
        ]
        t.labels = {"org.opencontainers.image.title": "Test Image"}
        tag1 = MagicMock()
        tag1.destination = "ghcr.io/posit-dev/test-image"
        tag1.suffix = "1.0.0"
        tag1.__str__ = lambda self: "ghcr.io/posit-dev/test-image:1.0.0"
        t.tags = StringableList([tag1])
        return t

    return _make


class TestCommandRunnerSeam:
    def test_run_routes_built_command_through_runner(self):
        cmd = OrasManifestIndexCreate(
            oras_bin="oras",
            sources=["ghcr.io/posit-dev/test/tmp@sha256:digest"],
            destination="ghcr.io/posit-dev/test/tmp:tag",
        )
        runner = StubRunner([_ok(cmd.command)])
        result = cmd.run(runner=runner)
        assert runner.calls[0][0] == cmd.command
        assert result.returncode == 0

    def test_run_raises_tool_error_on_runner_failure(self):
        cmd = OrasManifestIndexCreate(
            oras_bin="oras",
            sources=["ghcr.io/posit-dev/test/tmp@sha256:digest"],
            destination="ghcr.io/posit-dev/test/tmp:tag",
        )
        runner = StubRunner([_fail(cmd.command, stderr=b"manifest unknown")])
        with pytest.raises(BakeryToolRuntimeError) as exc:
            cmd.run(runner=runner)
        assert exc.value.tool_name == "oras"
        assert exc.value.exit_code == 1

    def test_run_forwards_step_label_to_runner(self):
        cmd = OrasManifestIndexCreate(
            oras_bin="oras",
            sources=["ghcr.io/posit-dev/test/tmp@sha256:digest"],
            destination="ghcr.io/posit-dev/test/tmp:tag",
        )
        runner = StubRunner([_ok(cmd.command)])
        cmd.run(runner=runner, step_label="index create")
        assert runner.calls[0][1].get("step_label") == "index create"


class TestWorkflowsThreadRunner:
    def test_index_create_workflow_uses_runner(self, mock_image_target_factory):
        target = mock_image_target_factory()
        wf = OrasIndexCreateWorkflow(oras_bin="oras", image_target=target, annotations={"k": "v"})
        runner = StubRunner([_ok(["oras", "manifest", "index", "create"])])
        result = wf.run(runner=runner)
        assert result.success is True
        assert runner.calls[0][0][:4] == ["oras", "manifest", "index", "create"]

    def test_index_copy_workflow_uses_runner(self, mock_image_target_factory):
        target = mock_image_target_factory()
        wf = OrasIndexCopyWorkflow(oras_bin="oras", image_target=target)
        runner = StubRunner([_ok(["oras", "cp"])])
        result = wf.run(source="ghcr.io/posit-dev/test-image/tmp:src", runner=runner)
        assert result.success is True
        assert runner.calls[0][0][:2] == ["oras", "cp"]

    def test_index_verify_workflow_uses_runner(self, mock_image_target_factory):
        target = mock_image_target_factory()
        wf = OrasIndexVerifyWorkflow(oras_bin="oras", image_target=target)
        runner = StubRunner([_ok(["oras", "manifest", "fetch"])])
        result = wf.run(runner=runner)
        assert result.success is True
        assert runner.calls[0][0][:3] == ["oras", "manifest", "fetch"]

    def test_index_create_workflow_failure_via_runner(self, mock_image_target_factory):
        target = mock_image_target_factory()
        wf = OrasIndexCreateWorkflow(oras_bin="oras", image_target=target)
        runner = StubRunner([_fail(["oras", "manifest", "index", "create"])])
        result = wf.run(runner=runner)
        assert result.success is False
        assert result.error is not None
