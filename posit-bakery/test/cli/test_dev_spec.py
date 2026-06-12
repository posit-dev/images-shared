"""Tests for --dev-spec / BAKERY_DEV_SPEC flag in build and ci matrix commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from posit_bakery.cli.main import app
from posit_bakery.config.image.dev_version.spec import DevBuildSpec
from posit_bakery.config.image.posit_product.const import ReleaseChannelEnum
from test.cli.conftest import settings_from_call

runner = CliRunner()
BASIC_CONTEXT = str(Path(__file__).parent.parent / "resources" / "basic")


class TestBuildDevSpec:
    def test_dev_spec_via_flag(self):
        """--dev-spec JSON is parsed and forwarded to BakerySettings."""
        with patch("posit_bakery.cli.build.BakeryConfig") as mock:
            instance = MagicMock()
            mock.from_context.return_value = instance
            result = runner.invoke(
                app,
                [
                    "build",
                    "--context",
                    BASIC_CONTEXT,
                    "--dev-versions",
                    "only",
                    "--dev-spec",
                    '{"version": "2026.05.0-dev+185-gSHA", "channel": "daily"}',
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 0, result.output
        settings = settings_from_call(mock)
        assert isinstance(settings.dev_spec, DevBuildSpec)
        assert settings.dev_spec.version == "2026.05.0-dev+185-gSHA"
        assert settings.dev_spec.channel == ReleaseChannelEnum.DAILY

    def test_dev_spec_via_env_var(self):
        """BAKERY_DEV_SPEC env var is equivalent to --dev-spec flag."""
        with patch("posit_bakery.cli.build.BakeryConfig") as mock:
            instance = MagicMock()
            mock.from_context.return_value = instance
            result = runner.invoke(
                app,
                ["build", "--context", BASIC_CONTEXT, "--dev-versions", "only"],
                env={"BAKERY_DEV_SPEC": '{"version": "2026.05.0-dev+185-gSHA"}'},
                catch_exceptions=False,
            )
        assert result.exit_code == 0, result.output
        settings = settings_from_call(mock)
        assert isinstance(settings.dev_spec, DevBuildSpec)
        assert settings.dev_spec.version == "2026.05.0-dev+185-gSHA"
        assert settings.dev_spec.channel is None

    def test_dev_spec_invalid_json_rejected(self):
        """Invalid JSON in --dev-spec causes a non-zero exit."""
        with patch("posit_bakery.cli.build.BakeryConfig") as mock:
            mock.from_context.return_value = MagicMock()
            result = runner.invoke(
                app,
                ["build", "--context", BASIC_CONTEXT, "--dev-spec", "not-json"],
            )
        assert result.exit_code != 0

    def test_dev_spec_invalid_schema_rejected(self):
        """JSON with unknown fields is rejected (extra='forbid' on DevBuildSpec)."""
        with patch("posit_bakery.cli.build.BakeryConfig") as mock:
            mock.from_context.return_value = MagicMock()
            result = runner.invoke(
                app,
                [
                    "build",
                    "--context",
                    BASIC_CONTEXT,
                    "--dev-spec",
                    '{"version": "1.0.0", "chanenl": "daily"}',
                ],
            )
        assert result.exit_code != 0

    def test_dev_spec_absent_is_none(self):
        """When --dev-spec is not passed, BakerySettings.dev_spec is None."""
        with patch("posit_bakery.cli.build.BakeryConfig") as mock:
            instance = MagicMock()
            mock.from_context.return_value = instance
            result = runner.invoke(
                app,
                ["build", "--context", BASIC_CONTEXT],
                catch_exceptions=False,
            )
        assert result.exit_code == 0, result.output
        settings = settings_from_call(mock)
        assert settings.dev_spec is None


class TestCiMatrixDevSpec:
    def test_dev_spec_via_flag(self):
        """--dev-spec JSON is parsed and forwarded to BakerySettings in ci matrix."""
        with patch("posit_bakery.cli.ci.BakeryConfig") as mock:
            instance = MagicMock()
            instance.model.images = []
            mock.from_context.return_value = instance
            result = runner.invoke(
                app,
                [
                    "ci",
                    "matrix",
                    "--context",
                    BASIC_CONTEXT,
                    "--dev-versions",
                    "only",
                    "--dev-spec",
                    '{"version": "2026.05.0-dev+185-gSHA", "channel": "daily"}',
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 0, result.output
        settings = settings_from_call(mock)
        assert isinstance(settings.dev_spec, DevBuildSpec)
        assert settings.dev_spec.version == "2026.05.0-dev+185-gSHA"
        assert settings.dev_spec.channel == ReleaseChannelEnum.DAILY

    def test_dev_spec_via_env_var(self):
        """BAKERY_DEV_SPEC env var works in ci matrix."""
        with patch("posit_bakery.cli.ci.BakeryConfig") as mock:
            instance = MagicMock()
            instance.model.images = []
            mock.from_context.return_value = instance
            result = runner.invoke(
                app,
                ["ci", "matrix", "--context", BASIC_CONTEXT, "--dev-versions", "only"],
                env={"BAKERY_DEV_SPEC": '{"version": "2026.05.0-dev+185-gSHA"}'},
                catch_exceptions=False,
            )
        assert result.exit_code == 0, result.output
        settings = settings_from_call(mock)
        assert isinstance(settings.dev_spec, DevBuildSpec)
        assert settings.dev_spec.version == "2026.05.0-dev+185-gSHA"
        assert settings.dev_spec.channel is None

    def test_dev_spec_invalid_json_rejected(self):
        """Invalid JSON in --dev-spec causes a non-zero exit in ci matrix."""
        with patch("posit_bakery.cli.ci.BakeryConfig") as mock:
            mock.from_context.return_value = MagicMock()
            result = runner.invoke(
                app,
                ["ci", "matrix", "--context", BASIC_CONTEXT, "--dev-spec", "not-json"],
            )
        assert result.exit_code != 0

    def test_dev_spec_invalid_schema_rejected(self):
        """JSON with unknown fields is rejected (extra='forbid' on DevBuildSpec)."""
        with patch("posit_bakery.cli.ci.BakeryConfig") as mock:
            mock.from_context.return_value = MagicMock()
            result = runner.invoke(
                app,
                [
                    "ci",
                    "matrix",
                    "--context",
                    BASIC_CONTEXT,
                    "--dev-spec",
                    '{"version": "1.0.0", "chanenl": "daily"}',
                ],
            )
        assert result.exit_code != 0

    def test_dev_spec_absent_is_none(self):
        """When --dev-spec is not passed, BakerySettings.dev_spec is None."""
        with patch("posit_bakery.cli.ci.BakeryConfig") as mock:
            instance = MagicMock()
            instance.model.images = []
            mock.from_context.return_value = instance
            result = runner.invoke(
                app,
                ["ci", "matrix", "--context", BASIC_CONTEXT],
                catch_exceptions=False,
            )
        assert result.exit_code == 0, result.output
        settings = settings_from_call(mock)
        assert settings.dev_spec is None


class TestDgossRunDevSpec:
    """Tests for --dev-spec / BAKERY_DEV_SPEC in bakery dgoss run."""

    def _invoke(self, extra_args: list[str], env: dict | None = None):
        with (
            patch("posit_bakery.plugins.builtin.dgoss.BakeryConfig") as mock_config,
            patch("posit_bakery.plugins.builtin.dgoss.DGossPlugin.execute", return_value=[]),
            patch("posit_bakery.plugins.builtin.dgoss.DGossPlugin.results"),
        ):
            instance = MagicMock()
            instance.base_path = Path(BASIC_CONTEXT)
            instance.targets = []
            mock_config.from_context.return_value = instance
            result = runner.invoke(
                app,
                ["dgoss", "run", "--context", BASIC_CONTEXT] + extra_args,
                env=env,
                catch_exceptions=False,
            )
            return result, mock_config

    def test_dev_spec_via_flag(self):
        """--dev-spec JSON is parsed and forwarded to BakerySettings in dgoss run."""
        result, mock = self._invoke(
            ["--dev-versions", "only", "--dev-spec", '{"version": "2026.05.0-dev+185-gSHA", "channel": "daily"}']
        )
        assert result.exit_code == 0, result.output
        settings = settings_from_call(mock)
        assert isinstance(settings.dev_spec, DevBuildSpec)
        assert settings.dev_spec.version == "2026.05.0-dev+185-gSHA"
        assert settings.dev_spec.channel == ReleaseChannelEnum.DAILY

    def test_dev_spec_via_env_var(self):
        """BAKERY_DEV_SPEC env var works in dgoss run."""
        result, mock = self._invoke(
            ["--dev-versions", "only"],
            env={"BAKERY_DEV_SPEC": '{"version": "2026.05.0-dev+185-gSHA"}'},
        )
        assert result.exit_code == 0, result.output
        settings = settings_from_call(mock)
        assert isinstance(settings.dev_spec, DevBuildSpec)
        assert settings.dev_spec.version == "2026.05.0-dev+185-gSHA"
        assert settings.dev_spec.channel is None

    def test_dev_spec_absent_is_none(self):
        """When --dev-spec is absent, BakerySettings.dev_spec is None."""
        result, mock = self._invoke([])
        assert result.exit_code == 0, result.output
        settings = settings_from_call(mock)
        assert settings.dev_spec is None

    def test_dev_spec_invalid_json_rejected(self):
        """Invalid JSON in --dev-spec causes a non-zero exit."""
        result, _ = self._invoke(["--dev-spec", "not-json"])
        assert result.exit_code != 0

    def test_dev_spec_invalid_schema_rejected(self):
        """JSON with unknown fields is rejected in dgoss run (extra='forbid' on DevBuildSpec)."""
        result, _ = self._invoke(["--dev-spec", '{"version": "1.0.0", "chanenl": "daily"}'])
        assert result.exit_code != 0

    def test_dev_channel_forwarded_to_settings(self):
        """--dev-channel is forwarded to BakerySettings.dev_channel."""
        result, mock = self._invoke(["--dev-versions", "only", "--dev-channel", "daily"])
        assert result.exit_code == 0, result.output
        settings = settings_from_call(mock)
        assert settings.dev_channel == ReleaseChannelEnum.DAILY
