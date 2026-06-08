"""Tests for the ContainerdImagePull helper."""

import subprocess
from unittest.mock import patch

import pytest

from posit_bakery.error import BakeryToolRuntimeError
from posit_bakery.plugins.builtin.soci.soci import ContainerdImagePull

pytestmark = [pytest.mark.unit]


def test_default_command():
    cmd = ContainerdImagePull(ctr_bin="ctr", image_ref="reg/img:tag")
    assert cmd.command == [
        "ctr",
        "--namespace",
        "default",
        "image",
        "pull",
        "reg/img:tag",
    ]


def test_with_namespace_address_and_platform():
    cmd = ContainerdImagePull(
        ctr_bin="/usr/local/bin/ctr",
        containerd_address="/run/containerd/alt.sock",
        containerd_namespace="moby",
        image_ref="reg/img:tag",
        all_platforms=True,
    )
    assert cmd.command == [
        "/usr/local/bin/ctr",
        "--address",
        "/run/containerd/alt.sock",
        "--namespace",
        "moby",
        "image",
        "pull",
        "--all-platforms",
        "reg/img:tag",
    ]


def test_run_success():
    cmd = ContainerdImagePull(ctr_bin="ctr", image_ref="reg/img:tag")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=cmd.command, returncode=0, stdout=b"", stderr=b"")
        cmd.run()
    mock_run.assert_called_once_with(cmd.command, capture_output=True)


def test_run_failure_raises():
    cmd = ContainerdImagePull(ctr_bin="ctr", image_ref="reg/img:tag")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=cmd.command, returncode=1, stdout=b"", stderr=b"boom")
        with pytest.raises(BakeryToolRuntimeError):
            cmd.run()


def test_sudo_prepends_prefix():
    cmd = ContainerdImagePull(ctr_bin="ctr", image_ref="reg/img:tag", sudo=True)
    assert cmd.command == [
        "sudo",
        "-n",
        "ctr",
        "--namespace",
        "default",
        "image",
        "pull",
        "reg/img:tag",
    ]


def test_no_sudo_by_default():
    cmd = ContainerdImagePull(ctr_bin="ctr", image_ref="reg/img:tag")
    assert cmd.command[0] == "ctr"


def test_dry_run_does_not_invoke_subprocess():
    cmd = ContainerdImagePull(ctr_bin="ctr", image_ref="reg/img:tag")
    with patch("subprocess.run") as mock_run:
        result = cmd.run(dry_run=True)
    mock_run.assert_not_called()
    assert result.returncode == 0
