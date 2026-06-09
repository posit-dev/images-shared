from pathlib import Path
from unittest.mock import MagicMock

import pytest

from posit_bakery import util
from posit_bakery.error import BakeryToolNotFoundError
from posit_bakery.util import SensitiveArg, display_command, exec_args

pytestmark = [
    pytest.mark.unit,
]


class TestSensitiveArg:
    def test_str_returns_redacted(self):
        assert str(SensitiveArg("real-secret")) == "***"

    def test_repr_returns_redacted(self):
        assert repr(SensitiveArg("real-secret")) == "SensitiveArg(***)"

    def test_value_returns_real_value(self):
        assert SensitiveArg("real-secret").value == "real-secret"

    def test_empty_string_value(self):
        assert SensitiveArg("").value == ""
        assert str(SensitiveArg("")) == "***"


class TestDisplayCommand:
    def test_plain_strings(self):
        assert display_command(["wizcli", "scan", "--no-color"]) == "wizcli scan --no-color"

    def test_redacts_sensitive_arg(self):
        cmd = ["wizcli", "--client-secret", SensitiveArg("tok")]
        assert display_command(cmd) == "wizcli --client-secret ***"
        assert "tok" not in display_command(cmd)

    def test_mixed_list(self):
        cmd = ["prog", SensitiveArg("s1"), "middle", SensitiveArg("s2")]
        result = display_command(cmd)
        assert result == "prog *** middle ***"
        assert "s1" not in result
        assert "s2" not in result

    def test_empty_list(self):
        assert display_command([]) == ""


class TestExecArgs:
    def test_unwraps_sensitive_arg(self):
        cmd = ["wizcli", "--client-secret", SensitiveArg("tok")]
        assert exec_args(cmd) == ["wizcli", "--client-secret", "tok"]

    def test_passes_through_plain_strings(self):
        cmd = ["prog", "arg1", "arg2"]
        assert exec_args(cmd) == ["prog", "arg1", "arg2"]

    def test_mixed_list(self):
        cmd = ["prog", SensitiveArg("s"), "plain"]
        assert exec_args(cmd) == ["prog", "s", "plain"]

    def test_empty_list(self):
        assert exec_args([]) == []


def test_find_bin_by_environ(mocker):
    """Test finding a binary by environment variable"""
    mocker.patch.dict("posit_bakery.util.os.environ", {"GOSS_PATH": "/usr/bin/goss"})
    assert util.find_bin("/tmp", "goss", "GOSS_PATH") == "/usr/bin/goss"


def test_find_bin_by_which(mocker):
    """Test finding a binary by which"""
    mocker.patch("posit_bakery.util.which", return_value="/usr/bin/goss")
    mocker.patch("os.environ.get", side_effect=[None, None])
    assert util.find_bin("/tmp", "goss", "GOSS_PATH") is None


def test_find_bin_by_context(tmpdir, mocker):
    """Test finding a binary by context tools directory"""
    mocker.patch("posit_bakery.util.which", return_value=None)
    mocker.patch("os.environ.get", side_effect=[None, None])
    tools = Path(tmpdir) / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    b = tools / "goss"
    b.touch(exist_ok=True)
    assert util.find_bin(tmpdir, "goss", "GOSS_PATH") == str(b)


def test_find_bin_not_found(tmpdir, mocker):
    """Test trying to find a binary that does not exist raises an error"""
    mocker.patch("posit_bakery.util.which", return_value=None)
    mocker.patch("os.environ.get", side_effect=[None, None])
    with pytest.raises(BakeryToolNotFoundError):
        util.find_bin(tmpdir, "goss", "GOSS_PATH")


def test_try_get_repo_url_ssh(mocker):
    """Test parsing a URL from an SSH remote"""
    mock_remote = MagicMock(config_reader={"url": "git@github.com:posit-dev/images-shared.git"})
    mock_repo = MagicMock(remotes=[mock_remote])
    mocker.patch("posit_bakery.util.git.Repo", return_value=mock_repo)
    assert util.try_get_repo_url("/tmp") == "github.com/posit-dev/images-shared"


def test_try_get_repo_url_https(mocker):
    """Test parsing a URL from an HTTPS remote"""
    mock_remote = MagicMock(config_reader={"url": "https://github.com/posit-dev/images-shared.git"})
    mock_repo = MagicMock(remotes=[mock_remote])
    mocker.patch("posit_bakery.util.git.Repo", return_value=mock_repo)
    assert util.try_get_repo_url("/tmp") == "github.com/posit-dev/images-shared"


def test_try_get_repo_url_no_remote(mocker):
    """Test returning a placeholder URL if there is no remote"""
    mock_repo = MagicMock(remotes=[])
    mocker.patch("posit_bakery.util.git.Repo", return_value=mock_repo)
    assert util.try_get_repo_url("/tmp") == "<REPLACE ME>"
