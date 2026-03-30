import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

import pydantic

from posit_bakery.error import BakeryToolRuntimeError, BakeryToolRuntimeErrorGroup
from posit_bakery.plugins.builtin.dgoss.command import DGossCommand
from posit_bakery.plugins.builtin.dgoss.errors import BakeryDGossError
from posit_bakery.plugins.builtin.dgoss.report import GossJsonReportCollection, GossJsonReport
from posit_bakery.image.image_target import ImageTarget

log = logging.getLogger(__name__)


class DGossSuite:
    def __init__(self, context: Path, image_targets: list[ImageTarget], platform: str | None = None) -> None:
        self.context = context
        self.image_targets = image_targets
        self.dgoss_commands = [DGossCommand.from_image_target(target, platform=platform) for target in image_targets]

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
            exit_code = p.returncode

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
                log.error(f"Failed to decode JSON output from dgoss for image '{str(dgoss_command.image_target)}': {e}")
                parse_err = e
            except pydantic.ValidationError as e:
                log.error(
                    f"Failed to load result data for summary from dgoss for image '{str(dgoss_command.image_target)}: {e}"
                )
                log.warning(f"Test results will be excluded from '{str(dgoss_command.image_target)}' in final summary.")
                parse_err = e

            if not parse_err:
                with open(results_file, "w") as f:
                    log.info(f"Writing results to {results_file}")
                    f.write(output)

            # Goss can exit 1 in multiple scenarios including test failures and incorrect configurations. From Bakery's
            # perspective, we only want to report an error back if the execution of Goss failed in some way. Our best
            # method of doing this is to check if both the exit code is non-zero, and we were unable to parse the output
            # of the command.
            if exit_code != 0 and parse_err is not None:
                log.error(f"dgoss for image '{str(dgoss_command.image_target)}' exited with code {exit_code}")
                errors.append(
                    BakeryDGossError(
                        f"dgoss execution failed for image '{str(dgoss_command.image_target)}'",
                        "dgoss",
                        cmd=dgoss_command.command,
                        stdout=p.stdout,
                        stderr=p.stderr,
                        parse_error=parse_err,
                        exit_code=exit_code,
                        metadata={"environment_variables": dgoss_command.dgoss_environment},
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
