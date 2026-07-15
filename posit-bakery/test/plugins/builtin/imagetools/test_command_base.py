"""Tests for the SociCommand base class and find_soci_bin."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import Field
from typing import Annotated

from posit_bakery.error import BakeryToolNotFoundError, BakeryToolRuntimeError
from posit_bakery.plugins.builtin.imagetools.soci import SociCommand, find_soci_bin

pytestmark = [pytest.mark.unit]


class _StubSociCommand(SociCommand):
    """Concrete SociCommand used to exercise the base class .run() path."""

    arg: Annotated[str, Field(description="A stub argument.")]

    @property
    def command(self) -> list[str]:
        return [self.soci_bin, "stub", self.arg]


def test_run_success():
    cmd = _StubSociCommand(soci_bin="soci", arg="x")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=cmd.command, returncode=0, stdout=b"ok", stderr=b"")
        result = cmd.run()
    mock_run.assert_called_once_with(cmd.command, capture_output=True)
    assert result.returncode == 0


def test_run_failure_raises_tool_error():
    cmd = _StubSociCommand(soci_bin="soci", arg="x")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=cmd.command, returncode=2, stdout=b"", stderr=b"boom")
        with pytest.raises(BakeryToolRuntimeError) as exc:
            cmd.run()
    assert exc.value.tool_name == "soci"
    assert exc.value.exit_code == 2


def test_dry_run_does_not_invoke_subprocess():
    cmd = _StubSociCommand(soci_bin="soci", arg="x")
    with patch("subprocess.run") as mock_run:
        result = cmd.run(dry_run=True)
    mock_run.assert_not_called()
    assert result.returncode == 0


def test_run_uses_runner_when_provided():
    cmd = _StubSociCommand(soci_bin="soci", arg="x")
    fake_runner = MagicMock()
    fake_runner.run.return_value = subprocess.CompletedProcess(args=cmd.command, returncode=0, stdout=b"ok", stderr=b"")

    result = cmd.run(runner=fake_runner)

    fake_runner.run.assert_called_once_with(cmd.command)
    assert result.returncode == 0


def test_run_falls_back_to_subprocess_when_runner_omitted():
    cmd = _StubSociCommand(soci_bin="soci", arg="x")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=cmd.command, returncode=0, stdout=b"", stderr=b"")
        cmd.run()
    mock_run.assert_called_once_with(cmd.command, capture_output=True)


def test_find_soci_bin_uses_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("SOCI_PATH", "/custom/soci")
    assert find_soci_bin(tmp_path) == "/custom/soci"


def test_find_soci_bin_falls_back_to_path_when_present(tmp_path, monkeypatch):
    monkeypatch.delenv("SOCI_PATH", raising=False)
    with patch("posit_bakery.util.which") as mock_which:
        mock_which.return_value = "/usr/local/bin/soci"
        # find_bin returns None when 'which' resolves, signaling "use the
        # bare name on PATH". find_soci_bin normalizes that to "soci".
        assert find_soci_bin(tmp_path) == "soci"


def test_find_soci_bin_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("SOCI_PATH", raising=False)
    with patch("posit_bakery.util.which") as mock_which:
        mock_which.return_value = None
        with pytest.raises(BakeryToolNotFoundError):
            find_soci_bin(tmp_path)
