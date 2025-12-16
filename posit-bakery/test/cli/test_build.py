import json
import re
import subprocess
from shutil import which

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

    filtered_platforms = [bakery_command.args[i + 1] for i, x in enumerate(bakery_command.args) if x == "--platform"]

    config = get_config_obj(suite_name)
    for target in config.targets:
        if filtered_platforms and all(
            re.search(filter_platform, target_platform) is None
            for filter_platform in filtered_platforms
            for target_platform in target.image_os.platforms
        ):
            continue
        for tag in target.tags:
            python_on_whales.docker.image.exists(tag)
            for label, value in target.labels.items():
                image = python_on_whales.docker.image.inspect(tag)
                assert label in image.config.labels
                assert image.config.labels[label] == value


@then(parsers.parse("the {suite_name} test suite built for platforms:"))
def check_multiplatform_build(resource_path, bakery_command, suite_name, get_config_obj, datatable):
    suite_path = resource_path / suite_name
    assert suite_path.is_dir()

    # FIXME(ianpittwood): python-on-whales does not yet support the --platform flag for `docker image inspect`, so we
    #                     have to shell out for now.
    #                     See https://github.com/gabrieldemarmiesse/python-on-whales/issues/692
    docker_path = which("docker")

    config = get_config_obj(suite_name)
    for target in config.targets:
        for tag in target.tags:
            for row in datatable:
                platform = row[0]
                if all(re.search(platform, target_platform) is None for target_platform in target.image_os.platforms):
                    continue
                proc = subprocess.run([docker_path, "image", "inspect", "--platform", platform, tag])
                assert proc.returncode == 0, f"Image {tag} not found for platform {platform}"


@then(parsers.parse("the {suite_name} test suite did not build for platforms:"))
def check_multiplatform_no_build(resource_path, bakery_command, suite_name, get_config_obj, datatable):
    suite_path = resource_path / suite_name
    assert suite_path.is_dir()

    # FIXME(ianpittwood): python-on-whales does not yet support the --platform flag for `docker image inspect`, so we
    #                     have to shell out for now.
    #                     See https://github.com/gabrieldemarmiesse/python-on-whales/issues/692
    docker_path = which("docker")

    config = get_config_obj(suite_name)
    for target in config.targets:
        for tag in target.tags:
            for row in datatable:
                platform = row[0]
                proc = subprocess.run([docker_path, "image", "inspect", "--platform", platform, tag])
                assert proc.returncode != 0, f"Image {tag} found for platform {platform}"


@then(parsers.parse("the {suite_name} test suite is not built"))
def check_build_artifacts_not_built(resource_path, bakery_command, suite_name, get_config_obj):
    suite_path = resource_path / suite_name
    assert suite_path.is_dir()

    config = get_config_obj(suite_name)
    for target in config.targets:
        for tag in target.tags:
            assert not python_on_whales.docker.image.exists(tag)
