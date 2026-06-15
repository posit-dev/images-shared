"""Unit tests for the `bakery dgoss run` CLI command.

Specifically guards the platform normalization step. If the caller passes a
value that already includes the `linux/` prefix, the command must not prepend
the prefix a second time. The shared GitHub Actions workflows pass platform
values straight through from `bakery ci matrix` output (e.g. `linux/amd64`),
and a double-prefixed value (e.g. `linux/linux/amd64`) causes Docker to
reject the run.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from posit_bakery.cli.main import app

runner = CliRunner()

BASIC_CONTEXT = str(Path(__file__).parent.parent.parent.parent / "resources" / "basic")


@pytest.fixture
def mocked_dgoss_run():
    """Mock BakeryConfig and DGossPlugin.execute so the CLI can run end-to-end
    without needing a Docker daemon or built images."""
    with patch("posit_bakery.plugins.builtin.dgoss.BakeryConfig") as mock_config:
        instance = MagicMock()
        instance.base_path = Path(BASIC_CONTEXT)
        # Non-empty so the zero-match guard does not abort the happy-path runs.
        instance.targets = [MagicMock()]
        mock_config.from_context.return_value = instance
        with (
            patch("posit_bakery.plugins.builtin.dgoss.DGossPlugin.execute") as mock_execute,
            patch("posit_bakery.plugins.builtin.dgoss.DGossPlugin.results"),
        ):
            mock_execute.return_value = []
            yield mock_config, mock_execute


class TestDgossRunPlatformNormalization:
    """Regression coverage: `--image-platform linux/amd64` must not become
    `linux/linux/amd64`."""

    @pytest.mark.parametrize(
        "given,expected",
        [
            ("amd64", "linux/amd64"),
            ("arm64", "linux/arm64"),
            ("linux/amd64", "linux/amd64"),
            ("linux/arm64", "linux/arm64"),
        ],
    )
    def test_normalizes_platform(self, mocked_dgoss_run, given, expected):
        mock_config, mock_execute = mocked_dgoss_run
        result = runner.invoke(
            app,
            ["dgoss", "run", "--context", BASIC_CONTEXT, "--image-platform", given],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mock_config.from_context.call_args[0][1]
        assert settings.filter.image_platform == [expected]
        assert mock_execute.call_args[1]["platform"] == expected


class TestDgossRunLatestFlag:
    """The --latest flag is passed through to settings and warns with dev inclusion."""

    def test_latest_passed_to_settings(self, mocked_dgoss_run):
        mock_config, _ = mocked_dgoss_run
        result = runner.invoke(
            app,
            ["dgoss", "run", "--latest", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mock_config.from_context.call_args[0][1]
        assert settings.latest is True

    def test_latest_default_false(self, mocked_dgoss_run):
        mock_config, _ = mocked_dgoss_run
        result = runner.invoke(
            app,
            ["dgoss", "run", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mock_config.from_context.call_args[0][1]
        assert settings.latest is False


class TestDgossRunImageVersionFilter:
    """Regression coverage: `--image-version` must reach the filter verbatim.

    ``BakeryConfigFilter.image_version`` is consumed by ``version_matches()``,
    which does segment-aware (not regex) matching, so the value must NOT be
    regex-escaped. Escaping a calver build string like ``2026.01.2+418.pro1``
    into ``2026\\.01\\.2\\+418\\.pro1`` made the filter match no versions, so
    `dgoss run` silently tested nothing and the CI workflow passed."""

    def test_image_version_passed_verbatim(self, mocked_dgoss_run):
        mock_config, _ = mocked_dgoss_run
        version = "2026.01.2+418.pro1"
        result = runner.invoke(
            app,
            ["dgoss", "run", "--context", BASIC_CONTEXT, "--image-version", version],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mock_config.from_context.call_args[0][1]
        assert settings.filter.image_version == version


class TestDgossRunZeroMatchGuard:
    """A filter that matches no targets must fail loudly, not silently pass.

    Before the guard, `dgoss run` with a non-matching filter exited 0 having
    tested nothing, hiding broken CI jobs."""

    def test_no_targets_exits_nonzero(self):
        with patch("posit_bakery.plugins.builtin.dgoss.BakeryConfig") as mock_config:
            instance = MagicMock()
            instance.base_path = Path(BASIC_CONTEXT)
            instance.targets = []
            mock_config.from_context.return_value = instance
            with patch("posit_bakery.plugins.builtin.dgoss.DGossPlugin.execute") as mock_execute:
                result = runner.invoke(
                    app,
                    ["dgoss", "run", "--context", BASIC_CONTEXT, "--image-version", "9999.99.99"],
                    catch_exceptions=False,
                )
        assert result.exit_code == 1
        assert "No image targets" in result.output
        assert "9999.99.99" in result.output
        mock_execute.assert_not_called()


class TestDgossRunJobsFlag:
    """The --jobs flag is forwarded to DGossPlugin.execute()."""

    def test_jobs_forwarded_to_execute(self, mocked_dgoss_run):
        _, mock_execute = mocked_dgoss_run
        result = runner.invoke(
            app,
            ["dgoss", "run", "--context", BASIC_CONTEXT, "--jobs", "2"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        assert mock_execute.call_args.kwargs["jobs"] == 2
