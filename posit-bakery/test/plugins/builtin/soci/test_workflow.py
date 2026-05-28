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
