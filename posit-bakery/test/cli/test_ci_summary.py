import json

import pytest
from typer.testing import CliRunner

from posit_bakery.cli.main import app

pytestmark = [pytest.mark.unit]

_WIDE_TERM_ENV = {"COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"}


def _write_summary_json(path, *, uid, platforms=1, tags=8, registry_size=None):
    path.write_text(
        json.dumps(
            {
                "targets": [
                    {
                        "uid": uid,
                        "image_name": "connect",
                        "version": "2026.01.1",
                        "os": "Ubuntu 24.04",
                        "variant": "Standard",
                        "platforms": platforms,
                        "tags": tags,
                        "layers": None,
                        "registry_size": registry_size,
                        "local_size": None,
                        "cache_ref": None,
                        "cache_size": None,
                    }
                ]
            }
        )
    )


def test_help_lists_output_and_disclaimer_flags():
    runner = CliRunner()
    result = runner.invoke(app, ["ci", "summary", "--help"], env=_WIDE_TERM_ENV)
    assert result.exit_code == 0
    assert "--output" in result.stdout
    assert "--disclaimer" in result.stdout


def test_renders_a_single_file_to_markdown(tmp_path):
    summary_file = tmp_path / "a.json"
    _write_summary_json(summary_file, uid="a", registry_size=100)
    output = tmp_path / "out.md"
    runner = CliRunner()

    result = runner.invoke(app, ["ci", "summary", str(summary_file), "--output", str(output)])

    assert result.exit_code == 0, result.stdout
    markdown = output.read_text()
    assert "connect" in markdown
    assert "100" in markdown or "B" in markdown  # rich.filesize formats bytes with a unit


def test_merges_two_files_for_the_same_uid_without_double_counting(tmp_path):
    amd64 = tmp_path / "amd64.json"
    arm64 = tmp_path / "arm64.json"
    _write_summary_json(amd64, uid="a", platforms=1, registry_size=100)
    _write_summary_json(arm64, uid="a", platforms=1, registry_size=150)
    output = tmp_path / "out.md"
    runner = CliRunner()

    result = runner.invoke(app, ["ci", "summary", str(amd64), str(arm64), "--output", str(output)])

    assert result.exit_code == 0, result.stdout
    markdown = output.read_text()
    assert "**Total (1 targets)**" in markdown  # one uid, not two


def test_disclaimer_is_written_into_the_output(tmp_path):
    summary_file = tmp_path / "a.json"
    _write_summary_json(summary_file, uid="a")
    output = tmp_path / "out.md"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "ci",
            "summary",
            str(summary_file),
            "--output",
            str(output),
            "--disclaimer",
            "This summary is incomplete.",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "This summary is incomplete." in output.read_text()
