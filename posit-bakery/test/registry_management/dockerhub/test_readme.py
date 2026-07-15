from unittest.mock import MagicMock, patch

import pytest

from posit_bakery.registry_management.dockerhub.readme import (
    _get_dockerhub_repos,
    check_readme_length,
    find_oversized_readmes,
    push_readmes,
    DOCKER_HUB_README_MAX_BYTES,
    DOCKER_HUB_README_USERNAME_ENV,
    DOCKER_HUB_README_PASSWORD_ENV,
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
    monkeypatch.setenv(DOCKER_HUB_README_USERNAME_ENV, "testuser")
    monkeypatch.setenv(DOCKER_HUB_README_PASSWORD_ENV, "testpass")


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


class TestCheckReadmeLength:
    def test_within_limit_returns_zero(self):
        assert check_readme_length("a" * 100, max_bytes=1000) == 0

    def test_at_limit_returns_zero(self):
        assert check_readme_length("a" * 1000, max_bytes=1000) == 0

    def test_over_limit_returns_overage(self):
        assert check_readme_length("a" * 1010, max_bytes=1000) == 10

    def test_counts_utf8_bytes_not_characters(self):
        # Each "e" with an acute accent is 1 character but 2 bytes in UTF-8, so
        # byte length diverges from len(content) well before the character count
        # would suggest a violation.
        content = "é" * 600  # 600 chars, 1200 bytes
        assert check_readme_length(content, max_bytes=1000) == 200

    def test_default_max_bytes_matches_dockerhub_limit(self):
        assert check_readme_length("a" * DOCKER_HUB_README_MAX_BYTES) == 0
        assert check_readme_length("a" * (DOCKER_HUB_README_MAX_BYTES + 1)) == 1


class TestFindOversizedReadmes:
    def test_no_violations_when_within_limit(self, tmp_targets, readme_env):
        for target in tmp_targets:
            readme_path = target.context.image_path / "README.md"
            readme_path.parent.mkdir(parents=True, exist_ok=True)
            readme_path.write_text("# Fine")

        assert find_oversized_readmes(tmp_targets) == []

    def test_reports_oversized_readme(self, tmp_targets, readme_env):
        oversized = "a" * (DOCKER_HUB_README_MAX_BYTES + 69)
        for target in tmp_targets:
            readme_path = target.context.image_path / "README.md"
            readme_path.parent.mkdir(parents=True, exist_ok=True)
            readme_path.write_text(oversized)

        violations = find_oversized_readmes(tmp_targets)
        assert len(violations) == 1
        assert "README.md" in violations[0]
        assert "69 bytes" in violations[0]

    def test_deduplicates_shared_readme(self, tmp_targets, readme_env):
        # Both Standard and Minimal variants share the same README.md; it should
        # only be reported once.
        oversized = "a" * (DOCKER_HUB_README_MAX_BYTES + 1)
        for target in tmp_targets:
            readme_path = target.context.image_path / "README.md"
            readme_path.parent.mkdir(parents=True, exist_ok=True)
            readme_path.write_text(oversized)

        assert len(find_oversized_readmes(tmp_targets)) == 1

    def test_ignores_non_eligible_targets(self, tmp_targets):
        for target in tmp_targets:
            target.image_version.latest = False
            target.image_version.isMatrixVersion = False
            readme_path = target.context.image_path / "README.md"
            readme_path.parent.mkdir(parents=True, exist_ok=True)
            readme_path.write_text("a" * (DOCKER_HUB_README_MAX_BYTES + 1))

        assert find_oversized_readmes(tmp_targets) == []

    def test_requires_no_credentials(self, tmp_targets, monkeypatch):
        monkeypatch.delenv(DOCKER_HUB_README_USERNAME_ENV, raising=False)
        monkeypatch.delenv(DOCKER_HUB_README_PASSWORD_ENV, raising=False)
        oversized = "a" * (DOCKER_HUB_README_MAX_BYTES + 1)
        for target in tmp_targets:
            readme_path = target.context.image_path / "README.md"
            readme_path.parent.mkdir(parents=True, exist_ok=True)
            readme_path.write_text(oversized)

        with patch("posit_bakery.registry_management.dockerhub.readme.DockerhubClient") as mock_client_cls:
            violations = find_oversized_readmes(tmp_targets)
            mock_client_cls.assert_not_called()

        assert len(violations) == 1


class TestPushReadmes:
    def test_skips_when_no_credentials(self, basic_targets, monkeypatch):
        monkeypatch.delenv(DOCKER_HUB_README_USERNAME_ENV, raising=False)
        monkeypatch.delenv(DOCKER_HUB_README_PASSWORD_ENV, raising=False)
        with patch("posit_bakery.registry_management.dockerhub.readme.DockerhubClient") as mock_client_cls:
            push_readmes(basic_targets)
            mock_client_cls.assert_not_called()

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

    def test_raises_on_oversized_readme_without_credentials(self, tmp_targets, monkeypatch):
        """The length check must fire before the credential check, so it also
        works in fork PR CI where no Docker Hub credentials are configured."""
        monkeypatch.delenv(DOCKER_HUB_README_USERNAME_ENV, raising=False)
        monkeypatch.delenv(DOCKER_HUB_README_PASSWORD_ENV, raising=False)
        oversized = "a" * (DOCKER_HUB_README_MAX_BYTES + 1)
        for target in tmp_targets:
            readme_path = target.context.image_path / "README.md"
            readme_path.parent.mkdir(parents=True, exist_ok=True)
            readme_path.write_text(oversized)

        with patch("posit_bakery.registry_management.dockerhub.readme.DockerhubClient") as mock_client_cls:
            with pytest.raises(ValueError, match="exceed Docker Hub's length limit"):
                push_readmes(tmp_targets)
            mock_client_cls.assert_not_called()

    def test_raises_on_oversized_readme_before_pushing(self, tmp_targets, readme_env):
        """Even with valid credentials, an oversized README must fail with a clear
        error instead of reaching Docker Hub's API and surfacing a raw HTTP 400."""
        oversized = "a" * (DOCKER_HUB_README_MAX_BYTES + 1)
        for target in tmp_targets:
            readme_path = target.context.image_path / "README.md"
            readme_path.parent.mkdir(parents=True, exist_ok=True)
            readme_path.write_text(oversized)

        with patch("posit_bakery.registry_management.dockerhub.readme.DockerhubClient") as mock_client_cls:
            with pytest.raises(ValueError, match="exceed Docker Hub's length limit"):
                push_readmes(tmp_targets)
            mock_client_cls.assert_not_called()
