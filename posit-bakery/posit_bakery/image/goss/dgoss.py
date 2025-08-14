import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Annotated, Self, Literal

import pydantic
from pydantic import BaseModel, Field, model_validator, computed_field

from posit_bakery.error import BakeryToolRuntimeError, BakeryToolRuntimeErrorGroup
from posit_bakery.image.goss.report import GossJsonReportCollection, GossJsonReport
from posit_bakery.image.image_target import ImageTargetContext, ImageTarget
from posit_bakery.util import find_bin

log = logging.getLogger(__name__)


def find_dgoss_bin(context: ImageTargetContext) -> str | None:
    """Find the path to the DGoss binary for the given image target's context.

    :param context: The context of the image target to search for the DGoss binary.
    """
    return find_bin(context.base_path, "dgoss", "DGOSS_PATH") or "dgoss"


def find_goss_bin(context: ImageTargetContext) -> str | None:
    """Find the path to the Goss binary for the given image target's context.

    :param context: The context of the image target to search for the Goss binary.
    """
    return find_bin(context.base_path, "goss", "GOSS_PATH")


def find_test_path(context: ImageTargetContext) -> Path | None:
    """Find the path to the Goss test directory for the given image target's context."""
    # Check for tests in the version path first
    tests_path = context.version_path / "test"
    if tests_path.exists():
        return tests_path

    # If not found, check in the image path
    tests_path = context.image_path / "test"
    if tests_path.exists():
        return tests_path

    # If not found, return None to indicate no tests found
    return None


class DGossCommand(BaseModel):
    image_target: ImageTarget
    dgoss_bin: Annotated[str, Field(default_factory=lambda data: find_dgoss_bin(data["image_target"].context))]
    goss_bin: Annotated[str | None, Field(default_factory=lambda data: find_goss_bin(data["image_target"].context))]
    dgoss_command: Annotated[str, Field(default="run")]
    version_mountpoint: Literal["/tmp/version"] = "/tmp/version"
    image_mountpoint: Literal["/tmp/image"] = "/tmp/image"
    project_mountpoint: Literal["/tmp/project"] = "/tmp/project"

    test_path: Annotated[Path | None, Field(default_factory=lambda data: find_test_path(data["image_target"].context))]
    wait: Annotated[int, Field(default=0)]
    image_command: Annotated[str, Field(default="sleep infinity")]

    @property
    def dgoss_environment(self) -> dict[str, str]:
        """Return the environment variables for the DGoss command."""
        env = {
            "GOSS_FILES_PATH": str(self.test_path),
            "GOSS_OPTS": "--format json --no-color",
        }
        if self.goss_bin:
            env["GOSS_BIN"] = self.goss_bin
        if self.wait > 0:
            env["GOSS_SLEEP"] = str(self.wait)
        return env

    @property
    def image_environment(self) -> dict[str, str]:
        """Return the environment variables for the DGoss command."""
        e = {
            "IMAGE_VERSION": self.image_target.image_version.name,
            "IMAGE_VERSION_MOUNT": str(self.version_mountpoint),
            "IMAGE_MOUNT": str(self.image_mountpoint),
            "PROJECT_MOUNT": str(self.project_mountpoint),
        }
        if self.image_target.image_variant:
            e["IMAGE_TYPE"] = self.image_target.image_variant.name
            e["IMAGE_VARIANT"] = self.image_target.image_variant.name
        if self.image_target.image_os:
            e["IMAGE_OS"] = self.image_target.image_os.name

        return e

    @property
    def volume_mounts(self) -> list[tuple[str, str]]:
        return [
            (str(self.image_target.context.version_path.absolute()), str(self.version_mountpoint)),
            (str(self.image_target.context.image_path.absolute()), str(self.image_mountpoint)),
            (str(self.image_target.context.base_path.absolute()), str(self.project_mountpoint)),
        ]

    @classmethod
    def from_image_target(cls, image_target: ImageTarget) -> "DGossCommand":
        args = {
            "image_target": image_target,
        }
        if image_target.image_version.parent:
            goss_options = image_target.image_version.parent.get_tool_option("goss")
            if goss_options:
                args["wait"] = goss_options.wait
                args["command"] = goss_options.command
        if image_target.image_variant:
            goss_options = image_target.image_variant.get_tool_option("goss")
            if goss_options:
                args["wait"] = goss_options.wait
                args["command"] = goss_options.command
        return cls(**args)

    @model_validator(mode="after")
    def validate(self) -> Self:
        """Validate the DGoss command configuration."""
        if not self.dgoss_bin:
            raise ValueError(
                "dgoss binary path must be specified with the `DGOSS_PATH` environment variable if it cannot be "
                "discovered in the system PATH."
            )
        if not self.test_path:
            raise ValueError(
                f"No test directory was found for target '{str(self.image_target)}'. Ensure the test directory "
                f"and test/goss.yaml file exist in either the version path or image path."
            )
        return self

    @computed_field
    @property
    def command(self) -> list[str]:
        """Return the full DGoss command to run."""
        cmd = [self.dgoss_bin, self.dgoss_command]
        for mount in self.volume_mounts:
            cmd.extend(["-v", f"{mount[0]}:{mount[1]}"])
        for env_var, value in self.image_environment.items():
            cmd.extend(["-e", f'{env_var}="{value}"'])
        cmd.append("--init")
        cmd.append(self.image_target.tags[0])
        cmd.extend(self.image_command.split())

        return cmd


class DGossSuite:
    def __init__(self, context: Path, image_targets: list[ImageTarget]):
        self.context = context
        self.image_targets = image_targets
        self.dgoss_commands = [DGossCommand.from_image_target(target) for target in image_targets]

    def run(self) -> tuple[GossJsonReportCollection, BakeryToolRuntimeError | BakeryToolRuntimeErrorGroup | None]:
        results_dir = self.context / "results" / "dgoss"
        if results_dir.exists():
            shutil.rmtree(results_dir)
        results_dir.mkdir(parents=True)

        report_collection = GossJsonReportCollection()
        errors = []

        for dgoss_command in self.dgoss_commands:
            log.info(f"[bright_blue bold]=== Running Goss tests for '{str(dgoss_command.image_target)}' ===")
            log.debug(f"[bright_black]Environment variables: {dgoss_command.dgoss_environment}")
            log.debug(f"[bright_black]Executing dgoss command: {' '.join(dgoss_command.command)}")

            run_env = os.environ.copy()
            run_env.update(dgoss_command.dgoss_environment)
            p = subprocess.run(dgoss_command.command, env=run_env, cwd=self.context, capture_output=True)

            image_subdir = results_dir / dgoss_command.image_target.image_name
            image_subdir.mkdir(parents=True, exist_ok=True)
            results_file = image_subdir / f"{dgoss_command.image_target.uid}.json"

            try:
                output = p.stdout.decode("utf-8")
                output = output.strip()
            except UnicodeDecodeError:
                log.warning(f"Unexpected encoding for dgoss output for image '{str(dgoss_command.image_target)}'.")
                output = p.stdout
            parse_err = None

            try:
                result_data = json.loads(output)
                output = json.dumps(result_data, indent=2)
                report_collection.add_report(
                    dgoss_command.image_target, GossJsonReport(filepath=results_file, **result_data)
                )
            except json.JSONDecodeError as e:
                log.warning(
                    f"Failed to decode JSON output from dgoss for image '{str(dgoss_command.image_target)}': {e}"
                )
                parse_err = e
            except pydantic.ValidationError as e:
                log.warning(
                    f"Failed to load result data for summary from dgoss for image '{str(dgoss_command.image_target)}: {e}"
                )
                log.warning(f"Test results will be excluded from '{str(dgoss_command.image_target)}' in final summary.")
                parse_err = e

            with open(results_file, "w") as f:
                log.info(f"Writing results to {results_file}")
                f.write(output)

            # Goss can exit 1 in multiple scenarios including test failures and incorrect configurations. From Bakery's
            # perspective, we only want to report an error back if the execution of Goss failed in some way. Our best
            # method of doing this is to check if both the exit code is non-zero, and we were unable to parse the output
            # of the command.
            exit_code = p.returncode
            if exit_code != 0 and parse_err is not None:
                log.error(f"dgoss for image '{str(dgoss_command.image_target)}' exited with code {exit_code}")
                errors.append(
                    BakeryToolRuntimeError(
                        f"Subprocess call to dgoss exited with code {exit_code}",
                        "dgoss",
                        cmd=dgoss_command.command,
                        stdout=p.stdout,
                        stderr=p.stderr,
                        exit_code=exit_code,
                        metadata={"results": results_file, "environment_variables": dgoss_command.dgoss_environment},
                    )
                )
            elif exit_code == 0:
                log.info(f"[bright_green bold]Goss tests passed for '{str(dgoss_command.image_target)}'")
            else:
                log.warning(f"[yellow bold]Goss tests failed for '{str(dgoss_command.image_target)}'")

        if errors:
            if len(errors) == 1:
                errors = errors[0]
            else:
                errors = BakeryToolRuntimeErrorGroup(f"dgoss runtime errors occurred for multiple images.", errors)
        else:
            errors = None
        return report_collection, errors
