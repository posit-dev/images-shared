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
