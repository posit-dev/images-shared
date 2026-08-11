import json
import re
import subprocess
from pathlib import Path
from shutil import which
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest
import python_on_whales
from pytest_bdd import scenarios, then, parsers
from typer.testing import CliRunner

from posit_bakery.cli.main import app
from posit_bakery.config.image.posit_product.errors import (
    ArtifactNotAvailableError,
    VersionSubstitutionError,
)
from posit_bakery.error import BakeryBuildErrorGroup, BakeryToolRuntimeError

scenarios(
    "cli/build.feature",
)

runner = CliRunner()

BASIC_CONTEXT = str(Path(__file__).parent.parent / "resources" / "basic")
# COLUMNS matters: Rich hard-wraps table/caption output, which would break substring assertions.
_ENV = {"TERM": "dumb", "NO_COLOR": "true", "COLUMNS": "200"}


@pytest.fixture
def mock_build_config():
    """Mock BakeryConfig in the build command to capture settings without building."""
    with patch("posit_bakery.cli.build.BakeryConfig") as mock:
        instance = MagicMock()
        instance.build_targets.return_value = None
        mock.from_context.return_value = instance
        yield mock


def _fake_target(
    platforms=("linux/amd64",),
    tags=("a", "b"),
    uid="fake-image-1.0.0-standard-ubuntu-22.04",
    image_name="fake-image",
    version="1.0.0",
    variant="Standard",
    os="Ubuntu 22.04",
):
    """A minimal stand-in for ImageTarget exposing only what BuildSummary reads."""
    return SimpleNamespace(
        uid=uid,
        image_name=image_name,
        image_version=SimpleNamespace(name=version),
        image_variant=SimpleNamespace(name=variant) if variant else None,
        image_os=SimpleNamespace(platforms=list(platforms), name=os) if os else None,
        tags=list(tags),
    )


class TestBuildErrorHandling:
    def test_artifact_not_available_exits_with_clean_message(self):
        """ArtifactNotAvailableError should print a plain message, not a traceback."""
        msg = "Artifact not available for version '2026.04.0-dev+5-gabcdef'"
        with patch("posit_bakery.cli.build.BakeryConfig") as mock:
            mock.from_context.side_effect = ArtifactNotAvailableError(msg)
            result = runner.invoke(app, ["build", "--context", BASIC_CONTEXT], catch_exceptions=False)

        assert result.exit_code == 1
        assert msg in result.output
        assert "Traceback" not in result.output

    def test_version_substitution_error_exits_with_clean_message(self):
        """VersionSubstitutionError should print a plain message, not a traceback."""
        msg = "Cannot substitute '2026.04.0-dev+5-gabcdef' into URL"
        with patch("posit_bakery.cli.build.BakeryConfig") as mock:
            mock.from_context.side_effect = VersionSubstitutionError(msg)
            result = runner.invoke(app, ["build", "--context", BASIC_CONTEXT], catch_exceptions=False)

        assert result.exit_code == 1
        assert msg in result.output
        assert "Traceback" not in result.output


class TestBuildZeroMatchGuard:
    """A filter that matches no targets must fail the build, not silently pass."""

    def test_no_targets_exits_nonzero(self):
        with patch("posit_bakery.cli.build.BakeryConfig") as mock:
            instance = MagicMock()
            instance.targets = []
            mock.from_context.return_value = instance
            result = runner.invoke(
                app,
                ["build", "--context", BASIC_CONTEXT, "--image-version", "9999.99.99"],
                catch_exceptions=False,
            )
        assert result.exit_code == 1
        assert "No image targets" in result.output
        assert "9999.99.99" in result.output
        instance.build_targets.assert_not_called()

    def test_no_targets_blocks_plan_output(self):
        """--plan must also fail rather than emit an empty bake plan."""
        with patch("posit_bakery.cli.build.BakeryConfig") as mock:
            instance = MagicMock()
            instance.targets = []
            mock.from_context.return_value = instance
            result = runner.invoke(
                app,
                ["build", "--plan", "--context", BASIC_CONTEXT, "--image-version", "9999.99.99"],
                catch_exceptions=False,
            )
        assert result.exit_code == 1
        assert "No image targets" in result.output
        instance.bake_plan_targets.assert_not_called()


class TestBuildLatestFlag:
    def test_latest_passed_to_settings(self, mock_build_config):
        result = runner.invoke(
            app,
            ["build", "--latest", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        settings = mock_build_config.from_context.call_args[0][1]
        assert settings.latest is True

    def test_latest_default_false(self, mock_build_config):
        result = runner.invoke(
            app,
            ["build", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        settings = mock_build_config.from_context.call_args[0][1]
        assert settings.latest is False


class TestBuildJobsFlag:
    def test_jobs_passed_to_build_targets(self, mock_build_config):
        instance = mock_build_config.from_context.return_value
        result = runner.invoke(
            app,
            ["build", "--jobs", "3", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert instance.build_targets.call_args.kwargs["jobs"] == 3

    def test_jobs_defaults_to_none(self, mock_build_config):
        instance = mock_build_config.from_context.return_value
        result = runner.invoke(
            app,
            ["build", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert instance.build_targets.call_args.kwargs["jobs"] is None


class TestBuildSummaryFlag:
    """`--summary` runs the build, then reports it. `--plan` is what makes it a dry run:
    `--plan --summary` prints counts without building, since nothing exists to measure."""

    def test_omitted_by_default(self, mock_build_config):
        instance = mock_build_config.from_context.return_value
        instance.targets = [_fake_target()]
        result = runner.invoke(app, ["build", "--context", BASIC_CONTEXT], catch_exceptions=False, env=_ENV)
        assert result.exit_code == 0
        assert "Build Summary" not in result.stderr

    def test_builds_then_prints_the_sizes_table(self, mock_build_config):
        """--summary builds first, then reports per-target sizes -- the size columns are the
        reason it has to build, and they only exist in the post-build view."""
        instance = mock_build_config.from_context.return_value
        instance.targets = [_fake_target()]
        result = runner.invoke(
            app, ["build", "--summary", "--context", BASIC_CONTEXT], catch_exceptions=False, env=_ENV
        )
        assert result.exit_code == 0
        instance.build_targets.assert_called_once()
        assert "Build Summary" in result.stderr
        assert "Registry Size" in result.stderr
        assert "Local Size" in result.stderr
        assert "Build Summary" not in result.stdout

    def test_format_json_builds_then_prints_to_stdout(self, mock_build_config):
        """Sizes are null here because the fake targets expose no ref() to measure -- the
        keys must still be present and null rather than absent or zero."""
        instance = mock_build_config.from_context.return_value
        instance.targets = [_fake_target()]
        result = runner.invoke(
            app,
            ["build", "--summary", "--summary-format", "json", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
            env=_ENV,
        )
        assert result.exit_code == 0
        instance.build_targets.assert_called_once()
        assert "Build Summary" not in result.stderr
        data = json.loads(result.stdout)
        assert data["build_targets"] == 1
        assert data["platform_builds"] == 1
        assert data["registry_tags"] == 2
        assert data["registry_size_bytes"] is None
        assert data["local_size_bytes"] is None
        assert len(data["targets"]) == 1

    def test_summary_is_still_emitted_when_the_build_fails(self, mock_build_config):
        """A partially failed build is exactly when the report is most useful, so the
        summary must survive the failure path -- without swallowing the failure itself."""
        instance = mock_build_config.from_context.return_value
        instance.targets = [_fake_target()]
        instance.build_targets.side_effect = BakeryBuildErrorGroup(
            "build failed",
            [BakeryToolRuntimeError("target failed", tool_name="docker", cmd=["docker", "build"])],
        )
        result = runner.invoke(
            app, ["build", "--summary", "--context", BASIC_CONTEXT], catch_exceptions=False, env=_ENV
        )
        assert result.exit_code == 1
        assert "Build failed" in result.stderr
        assert "Registry Size" in result.stderr

    def test_a_broken_summary_does_not_mask_the_build_failure(self, mock_build_config):
        """If the reporting path itself raises, the original build failure must still be the
        thing reported and exited on -- a bug in a report must never eat a build error."""
        instance = mock_build_config.from_context.return_value
        instance.targets = [_fake_target()]
        instance.build_targets.side_effect = BakeryToolRuntimeError("docker exploded")
        with patch(
            "posit_bakery.image.summary.BuildSummary.measure_sizes",
            side_effect=RuntimeError("summary is broken"),
        ):
            result = runner.invoke(
                app, ["build", "--summary", "--context", BASIC_CONTEXT], catch_exceptions=False, env=_ENV
            )
        assert result.exit_code == 1
        assert "Build failed" in result.stderr

    def test_platform_builds_sums_platforms_not_targets(self, mock_build_config):
        """A 2-platform target must count as 2 platform builds -- the whole point of this
        row is that it differs from the target count."""
        instance = mock_build_config.from_context.return_value
        instance.targets = [_fake_target(platforms=("linux/amd64", "linux/arm64"))]
        result = runner.invoke(
            app,
            ["build", "--summary", "--summary-format", "json", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
            env=_ENV,
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["build_targets"] == 1
        assert data["platform_builds"] == 2

    def test_image_platform_filter_narrows_platform_builds(self, mock_build_config):
        """--image-platform must narrow the *count* of platform builds, not just which
        targets survive -- a surviving multi-platform target keeps its full declared
        platforms list (config.py's filter is any-match, not narrowing), so the count has
        to apply the same override the real build uses instead of trusting the target."""
        instance = mock_build_config.from_context.return_value
        instance.targets = [_fake_target(platforms=("linux/amd64", "linux/arm64"))]
        result = runner.invoke(
            app,
            [
                "build",
                "--summary",
                "--summary-format",
                "json",
                "--image-platform",
                "linux/arm64",
                "--context",
                BASIC_CONTEXT,
            ],
            catch_exceptions=False,
            env=_ENV,
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["build_targets"] == 1
        assert data["platform_builds"] == 1

    def test_plan_with_summary_prints_plan_json_and_the_counts_table(self, mock_build_config):
        """--plan builds nothing, so there is nothing to measure: the counts view, not the
        sizes view, or every size column would be a dash."""
        instance = mock_build_config.from_context.return_value
        instance.targets = [_fake_target()]
        instance.bake_plan_targets.return_value = "{}"
        result = runner.invoke(
            app, ["build", "--plan", "--summary", "--context", BASIC_CONTEXT], catch_exceptions=False, env=_ENV
        )
        assert result.exit_code == 0
        assert "Build Summary" in result.stderr
        assert "Build Targets" in result.stderr
        assert "Registry Size" not in result.stderr
        assert json.loads(result.stdout) == {}
        instance.bake_plan_targets.assert_called_once()

    def test_format_json_with_plan_is_a_hard_error(self, mock_build_config):
        instance = mock_build_config.from_context.return_value
        instance.targets = [_fake_target()]
        result = runner.invoke(
            app,
            ["build", "--plan", "--summary", "--summary-format", "json", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
            env=_ENV,
        )
        assert result.exit_code == 1
        assert "not supported with --plan" in result.stderr
        instance.bake_plan_targets.assert_not_called()

    def test_plan_with_summary_does_not_build(self, mock_build_config):
        """--plan --summary shows bake JSON then the count table, with no build."""
        instance = mock_build_config.from_context.return_value
        instance.targets = [_fake_target()]
        instance.bake_plan_targets.return_value = "{}"
        result = runner.invoke(
            app, ["build", "--plan", "--summary", "--context", BASIC_CONTEXT], catch_exceptions=False, env=_ENV
        )
        assert result.exit_code == 0
        instance.build_targets.assert_not_called()


@then("the bake plan is valid", target_fixture="bake_plan_data")
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

    return plan


@then(parsers.parse("the bake plan has {num_targets} targets"))
def check_bake_plan_num_targets(num_targets, bake_plan_data):
    assert len(bake_plan_data["target"]) == int(num_targets)


@then(parsers.parse("the build summary shows {count:d} {metric}"))
def check_build_summary_metric(bakery_command, count: int, metric: str):
    label = metric.title()  # "platform builds" -> "Platform Builds", etc.
    assert re.search(rf"{label}\s*\W\s*{count}\b", bakery_command.result.stderr) is not None


@then("the targets include the commit hash")
def check_revision_label(bakery_command):
    plan = json.loads(bakery_command.result.stdout)

    label: str = "org.opencontainers.image.revision"
    for target in plan["target"].values():
        assert label in target["labels"]
        assert target["labels"][label]


@then(parsers.parse("the {suite_name} test suite is built"))
def check_build_artifacts(resource_path, bakery_command, suite_name, get_tmpconfig):
    suite_path = resource_path / suite_name
    assert suite_path.is_dir()

    filtered_platforms = [bakery_command.args[i + 1] for i, x in enumerate(bakery_command.args) if x == "--platform"]

    config = get_tmpconfig(suite_name)
    for target in config.targets:
        if filtered_platforms and all(
            re.search(filter_platform, target_platform) is None
            for filter_platform in filtered_platforms
            for target_platform in target.image_os.platforms
        ):
            continue
        for tag in target.tags.as_strings():
            python_on_whales.docker.image.exists(tag)
            for label, value in target.labels.items():
                image = python_on_whales.docker.image.inspect(tag)
                assert label in image.config.labels
                assert image.config.labels[label] == value


@then(parsers.parse("the {suite_name} test suite built for platforms:"))
def check_multiplatform_build(resource_path, bakery_command, suite_name, get_tmpconfig, datatable):
    suite_path = resource_path / suite_name
    assert suite_path.is_dir()

    # FIXME(ianpittwood): python-on-whales does not yet support the --platform flag for `docker image inspect`, so we
    #                     have to shell out for now.
    #                     See https://github.com/gabrieldemarmiesse/python-on-whales/issues/692
    docker_path = which("docker")

    config = get_tmpconfig(suite_name)
    for target in config.targets:
        for tag in target.tags.as_strings():
            for row in datatable:
                platform = row[0]
                if all(re.search(platform, target_platform) is None for target_platform in target.image_os.platforms):
                    continue
                proc = subprocess.run([docker_path, "image", "inspect", "--platform", platform, tag])
                assert proc.returncode == 0, f"Image {tag} not found for platform {platform}"


@then(parsers.parse("the {suite_name} test suite did not build for platforms:"))
def check_multiplatform_no_build(resource_path, bakery_command, suite_name, get_tmpconfig, datatable):
    suite_path = resource_path / suite_name
    assert suite_path.is_dir()

    # FIXME(ianpittwood): python-on-whales does not yet support the --platform flag for `docker image inspect`, so we
    #                     have to shell out for now.
    #                     See https://github.com/gabrieldemarmiesse/python-on-whales/issues/692
    docker_path = which("docker")

    config = get_tmpconfig(suite_name)
    for target in config.targets:
        for tag in target.tags.as_strings():
            for row in datatable:
                platform = row[0]
                proc = subprocess.run([docker_path, "image", "inspect", "--platform", platform, tag])
                assert proc.returncode != 0, f"Image {tag} found for platform {platform}"


@then(parsers.parse("the {suite_name} test suite is not built"))
def check_build_artifacts_not_built(resource_path, bakery_command, suite_name, get_tmpconfig):
    suite_path = resource_path / suite_name
    assert suite_path.is_dir()

    config = get_tmpconfig(suite_name)
    for target in config.targets:
        for tag in target.tags.as_strings():
            assert not python_on_whales.docker.image.exists(tag)


@then(parsers.parse("{metadata_file} contains build metadata for the {suite_name} test suite"))
def check_build_metadata(resource_path, bakery_command, metadata_file, suite_name, get_tmpconfig):
    metadata_path = bakery_command.context / metadata_file
    assert metadata_path.is_file()

    with open(metadata_path, "r") as f:
        data = json.load(f)

    config = get_tmpconfig(suite_name)

    expected_uids = [target.uid for target in config.targets].sort()
    actual_uids = list(data.keys()).sort()
    assert expected_uids == actual_uids

    for _, metadata in data.items():
        assert "image.name" in metadata
        assert re.search(r"[a-z0-9]+([._-][a-z0-9]+)*(:[a-zA-Z0-9._-]+)?", metadata["image.name"]) is not None
        assert "containerimage.digest" in metadata
        assert re.match(r"^sha256:[a-f0-9]{64}$", metadata["containerimage.digest"]) is not None
