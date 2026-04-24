"""Tests for the build retry functionality."""

from unittest.mock import MagicMock, patch

import pytest
from python_on_whales import DockerException

from posit_bakery.config.config import _retry_build, _RETRY_DELAY_SECONDS
from posit_bakery.error import BakeryFileError, BakeryToolRuntimeError

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


class TestRetryBuild:
    """Tests for the _retry_build helper function."""

    def test_successful_build_no_retry_needed(self):
        """Test that a successful build completes without retries."""
        mock_fn = MagicMock()

        _retry_build(mock_fn, retry=2, label="test-target")

        mock_fn.assert_called_once()

    @patch("posit_bakery.config.config.time.sleep")
    def test_retry_on_docker_exception_then_success(self, mock_sleep):
        """Test that DockerException triggers retry and succeeds on second attempt."""
        mock_fn = MagicMock(side_effect=[DockerException(["docker", "build"], 1), None])

        _retry_build(mock_fn, retry=1, label="test-target")

        assert mock_fn.call_count == 2
        mock_sleep.assert_called_once_with(_RETRY_DELAY_SECONDS)

    @patch("posit_bakery.config.config.time.sleep")
    def test_retry_on_bakery_tool_runtime_error_then_success(self, mock_sleep):
        """Test that BakeryToolRuntimeError triggers retry and succeeds on second attempt."""
        mock_fn = MagicMock(side_effect=[BakeryToolRuntimeError("Build failed", cmd=["docker", "build"]), None])

        _retry_build(mock_fn, retry=1, label="test-target")

        assert mock_fn.call_count == 2
        mock_sleep.assert_called_once_with(_RETRY_DELAY_SECONDS)

    @patch("posit_bakery.config.config.time.sleep")
    def test_all_retries_exhausted_raises_exception(self, mock_sleep):
        """Test that exception is raised when all retries are exhausted."""
        error = DockerException(["docker", "build"], 1)
        mock_fn = MagicMock(side_effect=error)

        with pytest.raises(DockerException):
            _retry_build(mock_fn, retry=2, label="test-target")

        assert mock_fn.call_count == 3  # initial + 2 retries
        assert mock_sleep.call_count == 2

    def test_bakery_file_error_not_retried(self):
        """Test that BakeryFileError is never retried."""
        error = BakeryFileError("File not found", filepath="/path/to/file")
        mock_fn = MagicMock(side_effect=error)

        with pytest.raises(BakeryFileError):
            _retry_build(mock_fn, retry=3, label="test-target")

        # Should only be called once, no retries
        mock_fn.assert_called_once()

    @patch("posit_bakery.config.config.time.sleep")
    def test_retry_zero_means_no_retries(self, mock_sleep):
        """Test that retry=0 means no retries, just one attempt."""
        error = DockerException(["docker", "build"], 1)
        mock_fn = MagicMock(side_effect=error)

        with pytest.raises(DockerException):
            _retry_build(mock_fn, retry=0, label="test-target")

        mock_fn.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("posit_bakery.config.config.time.sleep")
    def test_multiple_retries_then_success(self, mock_sleep):
        """Test multiple failures before eventual success."""
        mock_fn = MagicMock(
            side_effect=[
                DockerException(["docker", "build"], 1),
                BakeryToolRuntimeError("Network error", cmd=["docker", "push"]),
                None,  # Success on third attempt
            ]
        )

        _retry_build(mock_fn, retry=2, label="test-target")

        assert mock_fn.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("posit_bakery.config.config.time.sleep")
    def test_logs_warning_on_retry(self, mock_sleep, caplog):
        """Test that a warning is logged when retrying."""
        import logging

        caplog.set_level(logging.WARNING)
        mock_fn = MagicMock(side_effect=[DockerException(["docker", "build"], 1), None])

        _retry_build(mock_fn, retry=1, label="my-test-target")

        assert "Build failed for 'my-test-target'" in caplog.text
        assert "attempt 1/2" in caplog.text
        assert f"Retrying in {_RETRY_DELAY_SECONDS}s" in caplog.text
