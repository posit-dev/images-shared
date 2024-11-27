from pathlib import Path
from unittest.mock import MagicMock

import pytest

from posit_bakery import util
from posit_bakery.error import BakeryFileNotFoundError

pytestmark = [
    pytest.mark.unit,
]


def test_find_bin_by_environ(mocker):
    """Test finding a binary by environment variable"""
    mocker.patch.dict("posit_bakery.util.os.environ", {"GOSS_PATH": "/usr/bin/goss"})
    assert util.find_bin("/tmp", "goss", "GOSS_PATH") == "/usr/bin/goss"


def test_find_bin_by_which(mocker):
    """Test finding a binary by which"""
    mocker.patch("posit_bakery.util.which", return_value="/usr/bin/goss")
    assert util.find_bin("/tmp", "goss", "GOSS_PATH") is None


def test_find_bin_by_context(tmpdir, mocker):
    """Test finding a binary by context tools directory"""
    mocker.patch("posit_bakery.util.which", return_value=None)
    mocker.patch.dict("posit_bakery.util.os.environ", {})
    tools = Path(tmpdir) / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    b = tools / "goss"
    b.touch(exist_ok=True)
    assert util.find_bin(tmpdir, "goss", "GOSS_PATH") == str(b)


def test_find_bin_not_found(tmpdir, mocker):
    """Test trying to find a binary that does not exist raises an error"""
    mocker.patch("posit_bakery.util.which", return_value=None)
    mocker.patch.dict("posit_bakery.util.os.environ", {})
    with pytest.raises(BakeryFileNotFoundError):
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
