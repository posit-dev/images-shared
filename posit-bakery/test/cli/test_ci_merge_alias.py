"""Tests for the `bakery ci merge` back-compat alias."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from posit_bakery.cli.main import app

pytestmark = [pytest.mark.unit]


def test_merge_delegates_to_publish(tmp_path):
    runner = CliRunner()
    metadata_file = tmp_path / "fake-metadata.json"
    metadata_file.write_text("{}")

    with patch("posit_bakery.cli.ci.publish") as mock_publish:
        runner.invoke(app, ["ci", "merge", str(metadata_file)])
        assert mock_publish.called
        call_kwargs = mock_publish.call_args.kwargs
        # SOCI is config-driven now; the alias no longer passes a soci flag.
        assert "enable_soci" not in call_kwargs
