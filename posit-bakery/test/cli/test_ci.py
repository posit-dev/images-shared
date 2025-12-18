import json
import re

from pytest_bdd import scenarios, then, parsers, given
from python_on_whales.components.buildx.imagetools.models import Manifest

from posit_bakery.image import ImageTarget

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

    def patched_merge_method(self, sources: list[str], dry_run: bool = False) -> Manifest:
        calls.append((sources, dry_run))
        return Manifest(
            schemaVersion=2,
            mediaType="application/vnd.docker.distribution.manifest.v2+json",
        )

    mocker.patch.object(ImageTarget, "merge", patched_merge_method)
    return calls


@then("the files read include:")
def check_log_metadata_targets(command_logs, datatable):
    for row in datatable:
        assert re.search(f"Reading targets from .*{row[0]}", command_logs.text)


@then(parsers.parse("{num_targets} targets are found in the metadata"))
def check_log_metadata_targets(command_logs, num_targets):
    assert f"Found {num_targets} targets" in command_logs.text


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
