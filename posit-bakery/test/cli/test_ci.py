import json
import logging
import re
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_bdd import scenarios, then, parsers, given

from posit_bakery.cli.ci import _resolve_changed_files
from posit_bakery.config.config import version_matches
from posit_bakery.config.image.version import ImageVersion

from posit_bakery.plugins.protocol import ToolCallResult

scenarios(
    "cli/ci/matrix.feature",
    "cli/ci/merge.feature",
)


@then(parsers.parse("the matrix matches testdata {testdata_file}"))
def check_matrix_output(bakery_command, ci_testdata, testdata_file):
    testdata_file = ci_testdata / testdata_file
    expected_matrix = json.loads(testdata_file.read_text().strip())
    actual_matrix = json.loads(bakery_command.result.stdout.strip())
    assert actual_matrix == expected_matrix


@given(parsers.parse("with changed files in {filename}:"))
def write_changed_files_to_context(bakery_command, filename, datatable):
    changed_file_path = bakery_command.context / filename
    lines = [row[0] for row in datatable]
    changed_file_path.write_text("\n".join(lines) + "\n")
    bakery_command.add_args(["--changed-files-from", str(changed_file_path)])


@given(parsers.parse("with testdata {testdata_path} copied to context"))
def copy_ci_testdata_to_context(bakery_command, ci_testdata, testdata_path):
    testdata_source = ci_testdata / testdata_path
    if testdata_source.is_dir():
        for item in testdata_source.glob("**/*"):
            if item.is_file():
                relative_path = item.relative_to(testdata_source)
                target_path = bakery_command.context / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(item.read_bytes())
    else:
        target_path = bakery_command.context / testdata_source.name
        target_path.write_bytes(testdata_source.read_bytes())


@given("with image target merge method patched", target_fixture="ci_patched_merge_method_calls")
def patch_image_target_merge_method(mocker):
    calls = []

    # Track calls to OrasIndexCreateWorkflow and OrasIndexCopyWorkflow
    class MockOrasIndexCreateWorkflow:
        def __init__(self, oras_bin, image_target, annotations, plain_http=False):
            self.image_target = image_target
            self.oras_bin = oras_bin
            self.annotations = annotations
            self.plain_http = plain_http

        def run(self, dry_run=False, runner=None):
            sources = self.image_target.get_merge_sources()
            calls.append((sources, dry_run))
            result = MagicMock()
            result.success = True
            result.temp_ref = f"temp-ref-{self.image_target.uid}"
            return result

    class MockOrasIndexCopyWorkflow:
        def __init__(self, oras_bin, image_target):
            self.image_target = image_target
            self.oras_bin = oras_bin

        def run(self, source, dry_run=False):
            result = MagicMock()
            result.success = True
            return result

    class MockOrasIndexVerifyWorkflow:
        def __init__(self, oras_bin, image_target):
            self.image_target = image_target
            self.oras_bin = oras_bin

        def run(self, dry_run=False):
            result = MagicMock()
            result.success = True
            result.verified = self.image_target.tags.as_strings()
            return result

    class MockOrasWaitForSourcesWorkflow:
        def __init__(self, oras_bin, sources, **kwargs):
            self.oras_bin = oras_bin
            self.sources = sources

        def run(self, dry_run=False, **kwargs):
            result = MagicMock()
            result.success = True
            result.ready = list(self.sources)
            result.missing = []
            result.waited_seconds = 0.0
            return result

    # Patch the imports inside the publish function
    mocker.patch(
        "posit_bakery.plugins.builtin.imagetools.oras.OrasWaitForSourcesWorkflow",
        MockOrasWaitForSourcesWorkflow,
    )
    mocker.patch(
        "posit_bakery.plugins.builtin.imagetools.oras.OrasIndexCreateWorkflow",
        MockOrasIndexCreateWorkflow,
    )
    mocker.patch(
        "posit_bakery.plugins.builtin.imagetools.oras.OrasIndexCopyWorkflow",
        MockOrasIndexCopyWorkflow,
    )
    mocker.patch(
        "posit_bakery.plugins.builtin.imagetools.oras.OrasIndexVerifyWorkflow",
        MockOrasIndexVerifyWorkflow,
    )
    mocker.patch(
        "posit_bakery.plugins.builtin.imagetools.oras.find_oras_bin",
        return_value="/mock/oras",
    )
    return calls


@then("the files read include:")
def check_log_metadata_targets(command_logs, datatable):
    for row in datatable:
        assert re.search(f"Reading targets from .*{row[0]}", command_logs.text)


@then(parsers.parse("{num_targets} targets are found in the metadata"))
def check_log_metadata_targets(command_logs, num_targets):
    assert f"Found {num_targets} targets" in command_logs.text


@then(parsers.parse("{num_verified:d} destination tags are verified"))
def check_log_verified_targets(command_logs, num_verified):
    assert command_logs.text.count("Verified '") == num_verified


@then("the merge calls include:")
def check_log_metadata_targets(bakery_command, datatable, ci_patched_merge_method_calls):
    calls = [call[0] for call in ci_patched_merge_method_calls]
    expected_calls = []
    for row in datatable:
        call = []
        for col in row:
            col = col.strip()
            if col:
                call.append(col)
        expected_calls.append(call)

    for expected in expected_calls:
        assert expected in calls


def test_resolve_changed_files_warns_when_base_ref_also_given(tmp_path, caplog):
    """--changed-files-from overrides --base-ref; the override must not be silent.

    When both are supplied, --changed-files-from wins (its paths are used verbatim,
    no git is run), and a warning announces that --base-ref is ignored.
    """
    changes = tmp_path / "changed.txt"
    changes.write_text("app/template/Containerfile\n")

    with caplog.at_level(logging.WARNING, logger="posit_bakery.cli.ci"):
        result = _resolve_changed_files(
            base_ref="origin/main",
            changed_files_from=str(changes),
            rebase_root=tmp_path,
        )

    assert result == ["app/template/Containerfile"]
    assert any("--base-ref" in record.message and "ignored" in record.message.lower() for record in caplog.records), (
        f"expected a warning that --base-ref is ignored, got: {[r.message for r in caplog.records]}"
    )


def test_resolve_changed_files_falls_back_to_full_build_on_git_diff_error(tmp_path, mocker, caplog):
    """A git-diff failure (bad ref, unrelated histories, etc.) must fall back to a
    full build instead of crashing bakery ci matrix.

    This is what makes --base-ref safe to use on push events: on a branch's
    first-ever push, github.event.before is the all-zero SHA, which does not diff
    cleanly. classify_changes already fails safe to a full build for unrecognized
    paths; this extends the same philosophy to a broken base-ref.
    """
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    mocker.patch(
        "posit_bakery.config.changeset.git_changed_files",
        side_effect=subprocess.CalledProcessError(128, ["git", "diff", "--merge-base"]),
    )

    with caplog.at_level(logging.WARNING, logger="posit_bakery.cli.ci"):
        result = _resolve_changed_files(
            base_ref="0000000000000000000000000000000000000000",
            changed_files_from=None,
            rebase_root=tmp_path,
        )

    assert result is None
    assert any("falling back to a full build" in record.message.lower() for record in caplog.records), (
        f"expected a fallback warning, got: {[r.message for r in caplog.records]}"
    )


def test_resolve_changed_files_does_not_swallow_unrelated_errors(tmp_path, mocker):
    """Only subprocess.CalledProcessError is a recognized 'base_ref didn't diff
    cleanly' failure. Any other exception must propagate uncaught, proving the
    except clause above is exactly as narrow as intended and doesn't quietly
    mask unrelated bugs.
    """
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    mocker.patch(
        "posit_bakery.config.changeset.git_changed_files",
        side_effect=RuntimeError("unrelated bug, not a git-diff failure"),
    )

    with pytest.raises(RuntimeError, match="unrelated bug"):
        _resolve_changed_files(
            base_ref="some-ref",
            changed_files_from=None,
            rebase_root=tmp_path,
        )


class TestChangeAwareFlagIntersection:
    """Change-aware mode must still honor --dev-versions / --matrix-versions.

    The change set narrows the per-caller selection; it must not override the
    flags. Otherwise the production, development, and content PR jobs all build
    the same set instead of their disjoint slices.
    """

    def _run(self, resource_path, changed_files_path, *extra_args):
        from typer.testing import CliRunner
        from posit_bakery.cli.main import app as bakery_app

        runner = CliRunner()
        result = runner.invoke(
            bakery_app,
            [
                "ci",
                "matrix",
                "--quiet",
                "--context",
                str(resource_path / "changeset"),
                "--changed-files-from",
                str(changed_files_path),
                *extra_args,
            ],
            catch_exceptions=True,
            env={"TERM": "dumb", "NO_COLOR": "true"},
        )
        assert result.exit_code == 0, f"Command failed: {result.output}"
        return json.loads(result.stdout.strip())

    def test_matrix_only_skips_non_matrix_image(self, resource_path, tmp_path):
        """A release-dir change under --matrix-versions only must skip the non-matrix
        image entirely, instead of building it as if the flag were absent."""
        changed = tmp_path / "changed.txt"
        changed.write_text("app/1.0.0/Containerfile.ubuntu2204.std\n")

        matrix = self._run(resource_path, changed, "--matrix-versions", "only")

        assert matrix == [], f"expected the non-matrix image to be skipped, got: {matrix}"

    def test_template_change_excluded_under_dev_versions_exclude(self, mocker, resource_path, tmp_path):
        """A template-only change under --dev-versions exclude must build nothing: no
        release version was touched and dev versions are excluded. (The development
        job, with --dev-versions only, is what builds the dev versions.)"""
        fake_dev = ImageVersion(
            name="2026.01.0-dev+1-gABC",
            isDevelopmentVersion=True,
            subpath="dev",
            path=tmp_path,
        )
        mocker.patch(
            "posit_bakery.config.image.image.Image.load_dev_versions",
            lambda self_image: self_image.versions.append(fake_dev),
        )

        changed = tmp_path / "changed.txt"
        changed.write_text("app/template/Containerfile.ubuntu2204.jinja2\n")

        matrix = self._run(resource_path, changed, "--dev-versions", "exclude")

        assert matrix == [], f"expected an empty matrix under --dev-versions exclude, got: {matrix}"


class TestVersionMatches:
    @pytest.mark.parametrize(
        "ver_name,filter_version",
        [
            ("2026.03.1", "2026.03.1"),
            ("2026.05.0-dev+15-gSHA", "2026.05.0-dev+15-gSHA"),
            ("2026.05.0-dev+15-gSHA", "2026.05"),
            ("2026.05.0-dev+15-gSHA", "2026.05.0"),
            ("2026.05.0-dev+15-gSHA", "2026"),
            ("2026.03.1", "2026"),
            ("2026.03.1", "2026.03"),
            ("2026.05.0-dev+15-gSHA", "2026.05.0-dev"),
            ("R4.5.3-python3.14.3", "R4.5.3-python3.14.3"),
            ("R4.5.3-python3.14.3", "R4.5.3"),
        ],
    )
    def test_matches(self, ver_name, filter_version):
        assert version_matches(ver_name, filter_version)

    @pytest.mark.parametrize(
        "ver_name,filter_version",
        [
            ("2026.05.0-dev+15-gSHA", "2026.03"),
            ("2026.05.0-dev+15-gSHA", "2026.05.1"),
            ("2026.05.0-dev+15-gSHA", "2026.0"),
            ("2026.05.0-dev+15-gSHA", "20"),
            ("2026.05.0-dev+15-gSHA", "9999.99"),
            ("2026.03.1", "2026.03.1.0"),
            ("2026.05.0-dev+15-gSHA", "2026.05.0-rc"),
            ("2026.05.0", "2026.05.0-dev"),
            ("R4.5.3-python3.14.3", "R4.5.3-python3.13.0"),
        ],
    )
    def test_no_match(self, ver_name, filter_version):
        assert not version_matches(ver_name, filter_version)
