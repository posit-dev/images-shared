import json

import pytest
import python_on_whales
from pytest_bdd import scenarios, then, parsers

scenarios(
    "cli/build.feature",
)


@then("the bake plan is valid")
def check_bake_plan_json(bakery_command):
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
def check_revision_label(bakery_command):
    plan = json.loads(bakery_command.result.stdout)

    label: str = "org.opencontainers.image.revision"
    for target in plan["target"].values():
        assert label in target["labels"]
        assert target["labels"][label]


@then(parsers.parse("the {suite_name} test suite is built"))
def check_build_artifacts(resource_path, bakery_command, suite_name, get_config_obj):
    suite_path = resource_path / suite_name
    assert suite_path.is_dir()

    config = get_config_obj(suite_name)
    for target in config.targets:
        for tag in target.tags:
            python_on_whales.docker.image.exists(tag)
            for label, value in target.labels.items():
                image = python_on_whales.docker.image.inspect(tag)
                assert label in image.config.labels
                assert image.config.labels[label] == value
