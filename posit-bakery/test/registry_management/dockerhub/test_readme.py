from unittest.mock import MagicMock, patch

import pytest

from posit_bakery.registry_management.dockerhub.readme import (
    _get_dockerhub_repos,
    push_readmes,
    DOCKERHUB_README_USERNAME_ENV,
    DOCKERHUB_README_PASSWORD_ENV,
)


@pytest.fixture
def basic_targets(get_config_obj):
    return get_config_obj("basic").targets


@pytest.fixture
def tmp_targets(get_tmpconfig):
    """Targets backed by a temporary directory copy, safe for file creation/deletion."""
    return get_tmpconfig("basic").targets


@pytest.fixture
def readme_env(monkeypatch):
    """Set Docker Hub README credentials in the environment."""
    monkeypatch.setenv(DOCKERHUB_README_USERNAME_ENV, "testuser")
    monkeypatch.setenv(DOCKERHUB_README_PASSWORD_ENV, "testpass")


class TestGetDockerhubRepos:
    def test_extracts_dockerhub_repos(self, basic_targets):
        target = basic_targets[0]
        repos = _get_dockerhub_repos(target)
        assert ("posit", "test-image") in repos

    def test_excludes_ghcr(self, basic_targets):
        target = basic_targets[0]
        repos = _get_dockerhub_repos(target)
        for namespace, repo in repos:
            assert namespace != "posit-dev"


class TestPushReadmes:
    def test_raises_when_no_credentials(self, basic_targets, monkeypatch):
        monkeypatch.delenv(DOCKERHUB_README_USERNAME_ENV, raising=False)
        monkeypatch.delenv(DOCKERHUB_README_PASSWORD_ENV, raising=False)
        with pytest.raises(ValueError, match="credentials not configured"):
            push_readmes(basic_targets)

    def test_skips_non_latest_non_matrix_targets(self, tmp_targets, readme_env):
        for target in tmp_targets:
            target.image_version.latest = False
            target.image_version.isMatrixVersion = False

        # No eligible targets, so no client created, no error
        with patch("posit_bakery.registry_management.dockerhub.readme.DockerhubClient") as mock_client_cls:
            push_readmes(tmp_targets)
            mock_client_cls.assert_not_called()

    def test_allows_matrix_versions_without_latest(self, tmp_targets, readme_env):
        for target in tmp_targets:
            target.image_version.latest = False
            target.image_version.isMatrixVersion = True
            readme_path = target.context.image_path / "README.md"
            readme_path.parent.mkdir(parents=True, exist_ok=True)
            readme_path.write_text("# Matrix Image")

        mock_client = MagicMock()
        with patch(
            "posit_bakery.registry_management.dockerhub.readme.DockerhubClient",
            return_value=mock_client,
        ):
            push_readmes(tmp_targets)

        mock_client.update_full_description.assert_called_once_with("posit", "test-image", "# Matrix Image")

    def test_skips_dev_versions(self, tmp_targets, readme_env):
        for target in tmp_targets:
            target.image_version.isDevelopmentVersion = True

        with patch("posit_bakery.registry_management.dockerhub.readme.DockerhubClient") as mock_client_cls:
            push_readmes(tmp_targets)
            mock_client_cls.assert_not_called()

    def test_pushes_readme_for_eligible_target(self, tmp_targets, readme_env):
        readme_content = "# Test Image\nThis is a test."
        for target in tmp_targets:
            readme_path = target.context.image_path / "README.md"
            readme_path.parent.mkdir(parents=True, exist_ok=True)
            readme_path.write_text(readme_content)

        mock_client = MagicMock()
        with patch(
            "posit_bakery.registry_management.dockerhub.readme.DockerhubClient",
            return_value=mock_client,
        ):
            push_readmes(tmp_targets)

        mock_client.update_full_description.assert_called_once_with("posit", "test-image", readme_content)

    def test_deduplicates_by_repo(self, tmp_targets, readme_env):
        # Both Standard and Minimal variants point to the same Docker Hub repo
        for target in tmp_targets:
            readme_path = target.context.image_path / "README.md"
            readme_path.parent.mkdir(parents=True, exist_ok=True)
            readme_path.write_text("# Test Image")

        mock_client = MagicMock()
        with patch(
            "posit_bakery.registry_management.dockerhub.readme.DockerhubClient",
            return_value=mock_client,
        ):
            push_readmes(tmp_targets)

        assert mock_client.update_full_description.call_count == 1

    def test_raises_on_push_failure(self, tmp_targets, readme_env):
        for target in tmp_targets:
            readme_path = target.context.image_path / "README.md"
            readme_path.parent.mkdir(parents=True, exist_ok=True)
            readme_path.write_text("# Test")

        mock_client = MagicMock()
        mock_client.update_full_description.side_effect = Exception("API error")
        with patch(
            "posit_bakery.registry_management.dockerhub.readme.DockerhubClient",
            return_value=mock_client,
        ):
            with pytest.raises(RuntimeError, match="Failed to push READMEs"):
                push_readmes(tmp_targets)

    def test_skips_when_no_readme_file(self, tmp_targets, readme_env):
        mock_client = MagicMock()
        with patch(
            "posit_bakery.registry_management.dockerhub.readme.DockerhubClient",
            return_value=mock_client,
        ):
            push_readmes(tmp_targets)

        mock_client.update_full_description.assert_not_called()

    def test_raises_on_auth_failure(self, basic_targets, readme_env):
        with patch(
            "posit_bakery.registry_management.dockerhub.readme.DockerhubClient",
            side_effect=Exception("Auth failed"),
        ):
            with pytest.raises(Exception, match="Auth failed"):
                push_readmes(basic_targets)
