import json

from pytest_bdd import scenarios, then, parsers

scenarios("cli/get/tags.feature")


@then(parsers.parse("the tags match testdata {testdata_file}"))
def check_tags_output(bakery_command, ci_testdata, testdata_file):
    testdata_file = ci_testdata / testdata_file
    expected = json.loads(testdata_file.read_text().strip())
    actual = json.loads(bakery_command.result.stdout.strip())
    assert actual == expected
