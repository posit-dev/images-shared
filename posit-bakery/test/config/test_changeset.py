import subprocess
from pathlib import Path

import pytest

from posit_bakery.config.changeset import git_changed_files


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "base.txt").write_text("base\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "checkout", "-q", "-b", "feature")
    (repo / "connect" / "2026.05").mkdir(parents=True)
    (repo / "connect" / "2026.05" / "Containerfile").write_text("FROM scratch\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change")
    return repo


def test_git_changed_files_lists_paths_against_merge_base(temp_git_repo: Path):
    changed = git_changed_files(temp_git_repo, "main")
    assert "connect/2026.05/Containerfile" in changed
    assert "base.txt" not in changed


def test_git_changed_files_returns_posix_relative_paths(temp_git_repo: Path):
    changed = git_changed_files(temp_git_repo, "main")
    assert all(not c.startswith("/") for c in changed)
    assert all("\\" not in c for c in changed)
