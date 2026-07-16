import subprocess
import types
from pathlib import Path

import pytest

from posit_bakery.config import BakeryConfig
from posit_bakery.config.changeset import classify_changes, git_changed_files, git_show_file, ImageChangeSet
from posit_bakery.cli.ci import _version_selected


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


@pytest.fixture
def changeset_config(resource_path) -> BakeryConfig:
    return BakeryConfig(resource_path / "changeset" / "bakery.yaml")


def test_markdown_changes_are_ignored(changeset_config):
    sel = classify_changes(changeset_config, ["README.md", "app/README.md", "app/2.0.0/notes.md"])
    assert sel.full is False
    assert sel.images == {}


def test_bakery_yaml_change_forces_full(changeset_config):
    sel = classify_changes(changeset_config, ["bakery.yaml"])
    assert sel.full is True


def test_workflow_change_forces_full(changeset_config):
    sel = classify_changes(changeset_config, [".github/workflows/production.yml"])
    assert sel.full is True


def test_meta_files_are_ignored(changeset_config):
    sel = classify_changes(changeset_config, [".gitignore", ".idea/x.xml", ".github/ISSUE_TEMPLATE/bug.yml"])
    assert sel.full is False
    assert sel.images == {}


def test_version_dir_change_selects_that_version(changeset_config):
    sel = classify_changes(changeset_config, ["app/2.0.0/Containerfile.ubuntu2204.std"])
    assert sel.full is False
    assert set(sel.images.keys()) == {"app"}
    cs = sel.images["app"]
    assert cs.versions == {"2.0.0"}
    assert cs.include_dev is False
    assert cs.include_all_release is False


def test_template_change_selects_dev_versions(changeset_config):
    sel = classify_changes(changeset_config, ["app/template/Containerfile.ubuntu2204.jinja2"])
    assert set(sel.images.keys()) == {"app"}
    cs = sel.images["app"]
    assert cs.include_dev is True
    assert cs.versions == set()
    assert cs.include_all_release is False


def test_version_and_template_change_unions(changeset_config):
    sel = classify_changes(
        changeset_config,
        ["app/1.0.0/scripts/startup.sh", "app/template/deps/packages.txt.jinja2"],
    )
    cs = sel.images["app"]
    assert cs.versions == {"1.0.0"}
    assert cs.include_dev is True


def test_image_root_change_fails_safe_to_all_release(changeset_config):
    sel = classify_changes(changeset_config, ["app/some-shared-file.sh"])
    cs = sel.images["app"]
    assert cs.include_all_release is True


def test_matrix_image_change_selects_latest_and_dev(changeset_config):
    # content has a matrix but no declared dev versions -> latest slice only.
    sel = classify_changes(changeset_config, ["content/template/Containerfile.ubuntu2404.jinja2"])
    cs = sel.images["content"]
    assert cs.include_matrix_latest is True
    assert cs.include_dev is False


def test_unattributable_path_fails_safe_to_full(changeset_config):
    sel = classify_changes(changeset_config, ["scripts/shared-tool.sh"])
    assert sel.full is True


def _fake_ver(**kwargs) -> types.SimpleNamespace:
    """Create a minimal fake version object for _version_selected tests."""
    defaults = {
        "isDevelopmentVersion": False,
        "isMatrixVersion": False,
        "latest": False,
        "name": "1.0.0",
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


class TestVersionSelected:
    """Unit tests for the _version_selected helper in posit_bakery.cli.ci."""

    def test_dev_version_included_when_include_dev_true(self):
        ver = _fake_ver(isDevelopmentVersion=True)
        cs = ImageChangeSet(include_dev=True)
        assert _version_selected(ver, cs) is True

    def test_dev_version_excluded_when_include_dev_false(self):
        ver = _fake_ver(isDevelopmentVersion=True)
        cs = ImageChangeSet(include_dev=False)
        assert _version_selected(ver, cs) is False

    def test_matrix_latest_version_included_when_flag_and_latest(self):
        ver = _fake_ver(isMatrixVersion=True, latest=True)
        cs = ImageChangeSet(include_matrix_latest=True)
        assert _version_selected(ver, cs) is True

    def test_matrix_non_latest_version_excluded_even_when_flag(self):
        ver = _fake_ver(isMatrixVersion=True, latest=False)
        cs = ImageChangeSet(include_matrix_latest=True)
        assert _version_selected(ver, cs) is False

    def test_matrix_latest_version_excluded_when_flag_false(self):
        ver = _fake_ver(isMatrixVersion=True, latest=True)
        cs = ImageChangeSet(include_matrix_latest=False)
        assert _version_selected(ver, cs) is False

    def test_release_version_included_by_name(self):
        ver = _fake_ver(name="2.0.0")
        cs = ImageChangeSet(versions={"2.0.0"})
        assert _version_selected(ver, cs) is True

    def test_release_version_excluded_when_not_in_set(self):
        ver = _fake_ver(name="1.0.0")
        cs = ImageChangeSet(versions={"2.0.0"})
        assert _version_selected(ver, cs) is False

    def test_release_version_included_by_include_all_release(self):
        ver = _fake_ver(name="1.0.0")
        cs = ImageChangeSet(include_all_release=True)
        assert _version_selected(ver, cs) is True


def test_git_show_file_returns_content_at_ref(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "bakery.yaml").write_text("images: []\n")
    subprocess.run(["git", "add", "bakery.yaml"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)

    content = git_show_file(tmp_path, "HEAD", "bakery.yaml")

    assert content == "images: []\n"


def test_git_show_file_raises_on_missing_path(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "placeholder.txt").write_text("x")
    subprocess.run(["git", "add", "placeholder.txt"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)

    with pytest.raises(subprocess.CalledProcessError):
        git_show_file(tmp_path, "HEAD", "bakery.yaml")
