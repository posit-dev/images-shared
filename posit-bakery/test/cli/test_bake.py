import json

import pytest
from pytest_bdd import scenarios, given, when, then, parsers


scenarios("cli/bake.feature")


@then("the plan is valid")
def check_json(bakery_command):
    try:
        plan = json.loads(bakery_command.result.stdout)
    except json.JSONDecodeError:
        pytest.fail("bakery plan output is not valid JSON")

    assert "group" in plan
    assert isinstance(plan["group"], dict)
    assert "default" in plan["group"]
    assert isinstance(plan["group"]["default"], dict)
    assert "targets" in plan["group"]["default"]
    assert isinstance(plan["group"]["default"]["targets"], list)

    assert "target" in plan
    assert isinstance(plan["target"], dict)


@then("the targets include the commit hash")
def check_revision(bakery_command):
    plan = json.loads(bakery_command.result.stdout)

    label: str = "org.opencontainers.image.revision"
    for target in plan["target"].values():
        assert label in target["labels"]
        assert target["labels"][label]
