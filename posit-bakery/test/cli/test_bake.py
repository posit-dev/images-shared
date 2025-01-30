import json

import pytest
from pytest_bdd import scenarios, given, when, then, parsers


scenarios("cli/bake.feature")


@then("the output is valid JSON")
def check_json(bakery_command):
    try:
        json.loads(bakery_command.result.stdout)
    except json.JSONDecodeError:
        pytest.fail("bakery plan output is not valid JSON")


@then("the targets include the commit hash")
def check_revision(bakery_command):
    plan = json.loads(bakery_command.result.stdout)

    label: str = "org.opencontainers.image.revision"
    for target in plan["target"].values():
        assert label in target["labels"]
        assert target["labels"][label]
