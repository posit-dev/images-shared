"""Tests for SociConvertWorkflow."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.soci.options import SociOptions
from posit_bakery.plugins.builtin.soci.soci import SociConvertWorkflow

pytestmark = [pytest.mark.unit]


@pytest.fixture
def mock_target():
    t = MagicMock(spec=ImageTarget)
    t.image_name = "test-image"
    t.uid = "test-image-1-0-0"
    t.temp_registry = "ghcr.io/posit-dev"
    return t


@pytest.fixture
def workflow(mock_target):
    # The source/destination are registry refs; the OCI image layouts that
    # soci convert reads/writes are internal scratch.
    return SociConvertWorkflow(
        soci_bin="soci",
        oras_bin="oras",
        image_target=mock_target,
        options=SociOptions(enabled=True),
        source_ref="ghcr.io/posit-dev/test-image/tmp:merged",
    )


def _ok_proc(cmd):
    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")


def test_destination_ref_appends_soci_suffix(workflow):
    assert workflow.destination_ref == "ghcr.io/posit-dev/test-image/tmp:merged-soci"


def test_runs_oras_pull_convert_push_in_order(workflow):
    with (
        patch("subprocess.run") as mock_run,
        patch.object(SociConvertWorkflow, "_read_converted_digest", return_value="sha256:abc123"),
    ):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        result = workflow.run()

    assert result.success is True
    assert result.destination_ref == workflow.destination_ref
    # No containerd: no ctr pull, no soci push.
    # 3 calls: oras cp (registry -> layout), soci convert, oras cp (layout -> registry).
    assert mock_run.call_count == 3
    pull_args = mock_run.call_args_list[0].args[0]
    convert_args = mock_run.call_args_list[1].args[0]
    push_args = mock_run.call_args_list[2].args[0]

    assert pull_args[:2] == ["oras", "cp"]
    assert "--to-oci-layout" in pull_args
    assert pull_args[-2] == workflow.source_ref

    assert convert_args[:1] == ["soci"]
    assert "--standalone" in convert_args
    assert "--format" in convert_args
    assert "oci-dir" in convert_args

    assert push_args[:2] == ["oras", "cp"]
    assert "--from-oci-layout" in push_args
    # source is the converted layout referenced by digest; destination is the registry ref.
    assert push_args[-2].endswith("@sha256:abc123")
    assert push_args[-1] == workflow.destination_ref


def test_does_not_invoke_ctr(workflow):
    with (
        patch("subprocess.run") as mock_run,
        patch.object(SociConvertWorkflow, "_read_converted_digest", return_value="sha256:abc123"),
    ):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        workflow.run()

    for call in mock_run.call_args_list:
        assert call.args[0][:1] != ["ctr"]


def test_dry_run_does_not_invoke_subprocess(workflow):
    with patch("subprocess.run") as mock_run:
        result = workflow.run(dry_run=True)
    mock_run.assert_not_called()
    assert result.success is True


def test_pull_failure_returns_error(workflow):
    def fake_run(cmd, capture_output):
        # Fail on the first oras cp (registry -> layout pull).
        if cmd[:2] == ["oras", "cp"]:
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout=b"", stderr=b"pull boom")
        return _ok_proc(cmd)

    with patch("subprocess.run", side_effect=fake_run):
        result = workflow.run()

    assert result.success is False
    assert "pull boom" in (result.error or "")


def test_convert_failure_returns_error(workflow):
    def fake_run(cmd, capture_output):
        if "convert" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout=b"", stderr=b"convert boom")
        return _ok_proc(cmd)

    with patch("subprocess.run", side_effect=fake_run):
        result = workflow.run()

    assert result.success is False
    assert "convert boom" in (result.error or "")


def test_cleans_up_scratch_dir(workflow, tmp_path):
    scratch = tmp_path / "soci-scratch"

    with (
        patch("posit_bakery.plugins.builtin.soci.soci.tempfile.mkdtemp", return_value=str(scratch)) as mock_mkdtemp,
        patch("subprocess.run") as mock_run,
        patch.object(SociConvertWorkflow, "_read_converted_digest", return_value="sha256:abc123"),
    ):
        scratch.mkdir()
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        result = workflow.run()

    assert result.success is True
    mock_mkdtemp.assert_called_once()
    assert not scratch.exists()


def test_cleans_up_scratch_dir_on_failure(workflow, tmp_path):
    scratch = tmp_path / "soci-scratch"

    with (
        patch("posit_bakery.plugins.builtin.soci.soci.tempfile.mkdtemp", return_value=str(scratch)),
        patch("subprocess.run", side_effect=lambda cmd, capture_output: _ok_proc(cmd)),
        patch.object(SociConvertWorkflow, "_read_converted_digest", side_effect=RuntimeError("boom")),
    ):
        scratch.mkdir()
        with pytest.raises(RuntimeError):
            workflow.run()

    assert not scratch.exists()


def test_read_converted_digest_reads_index_json(workflow, tmp_path):
    layout = tmp_path / "out"
    layout.mkdir()
    (layout / "index.json").write_text('{"schemaVersion":2,"manifests":[{"digest":"sha256:deadbeef","size":7849}]}')
    assert workflow._read_converted_digest(layout) == "sha256:deadbeef"
