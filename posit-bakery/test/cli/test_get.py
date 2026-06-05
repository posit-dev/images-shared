import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pytest_bdd import scenarios, then, parsers
from typer.testing import CliRunner

from posit_bakery.cli.main import app

scenarios(
    "cli/get/tags.feature",
    "cli/get/version.feature",
)

runner = CliRunner()

BASIC_CONTEXT = str(Path(__file__).parent.parent / "resources" / "basic")


@then(parsers.parse("the tags match testdata {testdata_file}"))
def check_tags_output(bakery_command, ci_testdata, testdata_file):
    testdata_file = ci_testdata / testdata_file
    expected = json.loads(testdata_file.read_text().strip())
    actual = json.loads(bakery_command.result.stdout.strip())
    assert actual == expected


@pytest.fixture
def mocked_get_tags():
    """Mock BakeryConfig so `get tags` can run without loading a real config."""
    with patch("posit_bakery.cli.get.BakeryConfig") as mock_config:
        instance = MagicMock()
        instance.targets = []
        mock_config.from_context.return_value = instance
        yield mock_config


class TestGetTagsLatestFlag:
    """The --latest flag is passed through to settings and warns with dev inclusion."""

    def test_latest_passed_to_settings(self, mocked_get_tags):
        result = runner.invoke(
            app,
            ["get", "tags", "--latest", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mocked_get_tags.from_context.call_args[0][1]
        assert settings.latest is True

    def test_latest_default_false(self, mocked_get_tags):
        result = runner.invoke(
            app,
            ["get", "tags", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mocked_get_tags.from_context.call_args[0][1]
        assert settings.latest is False

    def test_latest_with_dev_versions_include_warns(self, mocked_get_tags, caplog):
        result = runner.invoke(
            app,
            ["get", "tags", "--latest", "--dev-versions", "include", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        assert "--latest ignores development versions" in caplog.text

    def test_no_warning_without_latest(self, mocked_get_tags, caplog):
        result = runner.invoke(
            app,
            ["get", "tags", "--dev-versions", "include", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        assert "--latest ignores development versions" not in caplog.text
