import json
import logging
import textwrap

from typer.testing import CliRunner

from posit_bakery.cli.main import app

runner = CliRunner()
_ENV = {"TERM": "dumb", "NO_COLOR": "true"}


def _write_config(tmp_path):
    config_file = tmp_path / "bakery.yaml"
    config_file.write_text(
        textwrap.dedent("""\
            repository:
              url: https://github.com/posit-dev/test
            images:
              - name: app
                versions:
                  - name: "1.0.0"
                    latest: true
                    os:
                      - name: Ubuntu 22.04
                        primary: true
                  - name: "2.0.0"
                    os:
                      - name: Ubuntu 22.04
                        primary: true
                  - name: "3.0.0"
                    os:
                      - name: Ubuntu 22.04
                        primary: true
                  - name: "4.0.0"
                    os:
                      - name: Ubuntu 22.04
                        primary: true
            """)
    )


def _matrix(tmp_path, *args):
    result = runner.invoke(
        app,
        ["ci", "matrix", "--context", str(tmp_path), *args],
        catch_exceptions=False,
        env=_ENV,
    )
    return result, json.loads(result.stdout)


def test_ci_matrix_recent_limits_release_versions(tmp_path):
    _write_config(tmp_path)

    result, matrix = _matrix(tmp_path, "--recent", "2")

    assert result.exit_code == 0
    assert {entry["version"] for entry in matrix} == {"4.0.0", "3.0.0"}


def test_ci_matrix_warns_when_changeset_version_is_excluded(tmp_path, caplog):
    _write_config(tmp_path)
    changed = tmp_path / "changed-files.txt"
    changed.write_text("app/1.0.0/Containerfile\n")

    with caplog.at_level(logging.WARNING):
        result, matrix = _matrix(
            tmp_path,
            "--recent",
            "2",
            "--changed-files-from",
            str(changed),
        )

    assert result.exit_code == 0
    assert matrix == []
    assert "Version '1.0.0' in image 'app' was modified in this changeset" in caplog.text
    assert "excluded by --recent 2" in caplog.text


def test_ci_matrix_recent_wins_over_full_release_changeset(tmp_path):
    _write_config(tmp_path)
    changed = tmp_path / "changed-files.txt"
    changed.write_text("app/unrecognized-file\n")

    result, matrix = _matrix(
        tmp_path,
        "--recent",
        "2",
        "--changed-files-from",
        str(changed),
    )

    assert result.exit_code == 0
    assert {entry["version"] for entry in matrix} == {"4.0.0", "3.0.0"}


def test_ci_matrix_does_not_blame_recent_for_dev_filter(tmp_path, caplog):
    """A recent release can be removed by --dev-versions only instead."""
    _write_config(tmp_path)
    changed = tmp_path / "changed-files.txt"
    changed.write_text("app/4.0.0/Containerfile\n")

    with caplog.at_level(logging.WARNING):
        result, matrix = _matrix(
            tmp_path,
            "--recent",
            "2",
            "--dev-versions",
            "only",
            "--changed-files-from",
            str(changed),
        )

    assert result.exit_code == 0
    assert matrix == []
    assert "Version '4.0.0' in image 'app' was modified" not in caplog.text
    assert "excluded by --recent" not in caplog.text


def test_ci_matrix_reports_filtered_image_version(tmp_path, caplog):
    _write_config(tmp_path)

    with caplog.at_level(logging.WARNING):
        result = runner.invoke(
            app,
            [
                "ci",
                "matrix",
                "--context",
                str(tmp_path),
                "--recent",
                "2",
                "--image-version",
                "1.0.0",
            ],
            catch_exceptions=False,
            env=_ENV,
        )

    assert result.exit_code == 1
    assert "matches --image-version filter but is being skipped" in caplog.text
    assert "No matrix entries matched --image-version '1.0.0'" in caplog.text
