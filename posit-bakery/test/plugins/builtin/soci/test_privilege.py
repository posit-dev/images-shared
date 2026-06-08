"""Tests for the sudo-prefix resolver."""

import subprocess
from unittest.mock import patch

import pytest

from posit_bakery.plugins.builtin.soci.soci import SociPrivilegeError, resolve_sudo_prefix

pytestmark = [pytest.mark.unit]


def test_root_needs_no_prefix():
    with patch("posit_bakery.plugins.builtin.soci.soci.os.geteuid", return_value=0):
        assert resolve_sudo_prefix() == []


def test_passwordless_sudo_returns_prefix():
    with (
        patch("posit_bakery.plugins.builtin.soci.soci.os.geteuid", return_value=1000),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        assert resolve_sudo_prefix() == ["sudo", "-n"]


def test_needs_password_raises():
    with (
        patch("posit_bakery.plugins.builtin.soci.soci.os.geteuid", return_value=1000),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"")
        with pytest.raises(SociPrivilegeError):
            resolve_sudo_prefix()
