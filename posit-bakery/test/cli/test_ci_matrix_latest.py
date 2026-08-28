"""Tests for the `latest` field emitted by `bakery ci matrix`.

CI workflows gate per-version scan steps on this field rather than passing `--latest`
to a command already pinned to a single version by the build matrix. That pin plus
`--latest` resolves to an empty target set on every non-latest version, which bakery
reports as an error.

Because consumers make the "is this the latest version" decision from this field rather
than from the filter, the two must agree. They share ImageVersion.is_latest_release so
they cannot drift; TestCiMatrixLatestMatchesFilter checks that end to end.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from posit_bakery.cli.main import app
from posit_bakery.config.config import BakeryConfig, BakerySettings
from posit_bakery.config.image.posit_product.const import ReleaseChannelEnum
from posit_bakery.const import DevVersionInclusionEnum

runner = CliRunner()
CHANGESET_CONTEXT = str(Path(__file__).parent.parent / "resources" / "changeset")


def _matrix(*args: str) -> list[dict]:
    result = runner.invoke(
        app,
        ["ci", "matrix", "--quiet", "--context", CHANGESET_CONTEXT, *args],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout.strip())


class TestCiMatrixLatestField:
    def test_marks_latest_version(self):
        """2.0.0 carries `latest: true` in the fixture; 1.0.0 does not."""
        entries = {e["version"]: e for e in _matrix() if e["image"] == "app"}

        assert entries["2.0.0"]["latest"] is True
        assert entries["1.0.0"]["latest"] is False

    def test_latest_is_json_boolean(self):
        """The workflow gates on this in a GHA `if:`, where a non-boolean is truthy."""
        for entry in _matrix():
            assert isinstance(entry["latest"], bool), entry

    def test_exclude_latest_omits_field(self):
        for entry in _matrix("--exclude", "latest"):
            assert "latest" not in entry
            # Excluding one field must not disturb the others.
            assert "version" in entry
            assert "dev" in entry


class TestCiMatrixLatestMatchesFilter:
    """The matrix field and the --latest filter must select the same versions.

    The workflow gates on the field while bakery's own filter is what any manual
    `--latest` invocation uses. If these drift, the scan silently covers the wrong
    set instead of failing, which is the one failure mode the gating approach can
    introduce.
    """

    def test_agrees_with_generate_image_targets(self):
        from_matrix = {e["version"] for e in _matrix() if e["image"] == "app" and e["latest"]}

        config = BakeryConfig.from_context(CHANGESET_CONTEXT, BakerySettings(latest=True))
        from_filter = {t.image_version.name for t in config.targets if t.image_name == "app"}

        assert from_matrix == from_filter
        assert from_matrix == {"2.0.0"}


class TestCiMatrixLatestDevVersions:
    """A dev version reports `latest: false`.

    The rule itself lives in ImageVersion.is_latest_release and is covered against real
    objects in test/config/image/test_version.py. This only checks that the matrix
    command plumbs the predicate through to the emitted field.
    """

    @pytest.fixture
    def mock_config_with_latest_dev_version(self):
        dev_ver = MagicMock()
        dev_ver.name = "2026.99.0-dev+1"
        dev_ver.isDevelopmentVersion = True
        dev_ver.latest = True
        # As ImageVersion.is_latest_release would resolve it for a dev version.
        dev_ver.is_latest_release = False
        dev_ver.metadata = {"release_channel": ReleaseChannelEnum.DAILY}
        dev_ver.supported_platforms = ["linux/amd64"]
        dev_ver.matches_dev_filter = lambda dev_versions, dev_channel=None: (
            (False, "excluded by --dev-versions exclude")
            if dev_versions == DevVersionInclusionEnum.EXCLUDE
            else (True, None)
        )

        img = MagicMock()
        img.name = "app"
        img.matrix = None
        img.versions = [dev_ver]

        with patch("posit_bakery.cli.ci.BakeryConfig") as mock:
            instance = MagicMock()
            instance.model.images = [img]
            mock.from_context.return_value = instance
            yield mock

    def test_dev_version_is_not_latest(self, mock_config_with_latest_dev_version):
        entries = _matrix("--dev-versions", "only")

        assert len(entries) == 1
        assert entries[0]["dev"] is True
        assert entries[0]["latest"] is False
