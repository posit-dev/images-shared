import json
import re
from unittest.mock import MagicMock

import pytest
from pytest_bdd import scenarios, then, parsers, given

from posit_bakery.config.config import version_matches

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

        def run(self, dry_run=False):
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
        "posit_bakery.plugins.builtin.oras.oras.OrasWaitForSourcesWorkflow",
        MockOrasWaitForSourcesWorkflow,
    )
    mocker.patch(
        "posit_bakery.plugins.builtin.oras.oras.OrasIndexCreateWorkflow",
        MockOrasIndexCreateWorkflow,
    )
    mocker.patch(
        "posit_bakery.plugins.builtin.oras.oras.OrasIndexCopyWorkflow",
        MockOrasIndexCopyWorkflow,
    )
    mocker.patch(
        "posit_bakery.plugins.builtin.oras.oras.OrasIndexVerifyWorkflow",
        MockOrasIndexVerifyWorkflow,
    )
    mocker.patch(
        "posit_bakery.plugins.builtin.oras.oras.find_oras_bin",
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
