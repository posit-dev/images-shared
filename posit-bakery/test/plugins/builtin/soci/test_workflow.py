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
    return SociConvertWorkflow(
        soci_bin="soci",
        ctr_bin="ctr",
        image_target=mock_target,
        options=SociOptions(enabled=True),
        source_ref="ghcr.io/posit-dev/test-image/tmp:merged",
    )


def test_destination_ref_appends_soci_suffix(workflow):
    assert workflow.destination_ref == "ghcr.io/posit-dev/test-image/tmp:merged-soci"


def test_run_executes_pull_convert_push_in_order(workflow):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        result = workflow.run()

    assert result.success is True
    assert result.destination_ref == workflow.destination_ref
    assert result.resolved_namespace == "default"
    # 3 calls: ctr pull, soci convert, soci push
    assert mock_run.call_count == 3
    pull_args = mock_run.call_args_list[0].args[0]
    convert_args = mock_run.call_args_list[1].args[0]
    push_args = mock_run.call_args_list[2].args[0]
    assert pull_args[:1] == ["ctr"]
    assert "pull" in pull_args
    assert convert_args[:1] == ["soci"]
    assert "convert" in convert_args
    assert push_args[:1] == ["soci"]
    assert "push" in push_args


def test_dry_run_does_not_invoke_subprocess(workflow):
    with patch("subprocess.run") as mock_run:
        result = workflow.run(dry_run=True)
    mock_run.assert_not_called()
    assert result.success is True


def _not_found_proc(cmd):
    return subprocess.CompletedProcess(
        args=cmd,
        returncode=1,
        stdout=b"",
        stderr=b'soci: image "x": not found',
    )


def _ok_proc(cmd):
    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")


def test_falls_back_to_second_namespace_on_not_found(workflow):
    # ctr pull defaults to namespace 'default'; we simulate not-found there
    # and success in 'moby'. ctr pull is the call that triggers the fallback.
    call_count = {"n": 0}

    def fake_run(cmd, capture_output):
        call_count["n"] += 1
        # First call: ctr pull in 'default' fails with not-found.
        if call_count["n"] == 1:
            return _not_found_proc(cmd)
        return _ok_proc(cmd)

    with patch("subprocess.run", side_effect=fake_run):
        result = workflow.run()

    assert result.success is True
    assert result.resolved_namespace == "moby"
    # ctr pull(default-fail) + ctr pull(moby-ok) + convert + push = 4
    assert call_count["n"] == 4


def test_non_not_found_error_short_circuits(workflow):
    def fake_run(cmd, capture_output):
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout=b"", stderr=b"network error")

    with patch("subprocess.run", side_effect=fake_run):
        result = workflow.run()

    assert result.success is False
    assert "network error" in (result.error or "")


def test_all_namespaces_not_found_returns_failure(workflow):
    with patch("subprocess.run", side_effect=lambda cmd, capture_output: _not_found_proc(cmd)):
        result = workflow.run()

    assert result.success is False
    assert "not found" in (result.error or "").lower()


@pytest.fixture
def standalone_workflow(mock_target):
    return SociConvertWorkflow(
        soci_bin="soci",
        ctr_bin="ctr",
        image_target=mock_target,
        options=SociOptions(enabled=True, standalone=True),
        source_ref="./img.tar",
        standalone=True,
    )


def test_standalone_mode_skips_ctr_pull_and_push(standalone_workflow):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        result = standalone_workflow.run()

    assert result.success is True
    # Only one call: soci convert. No ctr pull, no soci push (the caller is
    # responsible for pushing the resulting OCI layout via ORAS).
    assert mock_run.call_count == 1
    convert_cmd = mock_run.call_args.args[0]
    assert "--standalone" in convert_cmd


def test_standalone_destination_ref_is_sibling_path(standalone_workflow):
    assert standalone_workflow.destination_ref == "./img.tar-soci"
