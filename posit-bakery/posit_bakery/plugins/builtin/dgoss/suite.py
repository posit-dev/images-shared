import json
import logging
import os
import shutil
from pathlib import Path

import pydantic

from posit_bakery.error import BakeryToolRuntimeError, BakeryToolRuntimeErrorGroup
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.parallel import ParallelShellExecutor, ShellResult, ShellTask, resolve_max_workers
from posit_bakery.plugins.builtin.dgoss.command import DGossCommand
from posit_bakery.plugins.builtin.dgoss.errors import BakeryDGossError
from posit_bakery.plugins.builtin.dgoss.report import GossJsonReport, GossJsonReportCollection

log = logging.getLogger(__name__)


class DGossSuite:
    def __init__(
        self,
        context: Path,
        image_targets: list[ImageTarget],
        platform: str | None = None,
        jobs: int | None = None,
    ) -> None:
        self.context = context
        self.image_targets = image_targets
        self.dgoss_commands = [DGossCommand.from_image_target(target, platform=platform) for target in image_targets]
        self.max_workers = resolve_max_workers(jobs, len(self.dgoss_commands))

    def run(self) -> tuple[GossJsonReportCollection, BakeryToolRuntimeError | BakeryToolRuntimeErrorGroup | None]:
        results_dir = self.context / "results" / "dgoss"
        if results_dir.exists():
            shutil.rmtree(results_dir)
        results_dir.mkdir(parents=True)

        report_collection = GossJsonReportCollection()
        errors: list[BakeryToolRuntimeError] = []

        tasks: list[ShellTask] = []
        for dgoss_command in self.dgoss_commands:
            run_env = os.environ.copy()
            run_env.update(dgoss_command.dgoss_environment)
            tasks.append(
                ShellTask(
                    key=dgoss_command.image_target.uid,
                    cmd=dgoss_command.command,
                    env=run_env,
                    cwd=self.context,
                    label=str(dgoss_command.image_target),
                    payload=dgoss_command,
                )
            )

        def handle_result(result: ShellResult) -> None:
            """Process one finished dgoss run on the main thread: parse, persist, and log."""
            dgoss_command: DGossCommand = result.task.payload
            target = dgoss_command.image_target

            log.info(f"[bright_blue bold]=== Goss tests for '{str(target)}' ===")
            log.debug(f"[bright_black]Environment variables: {dgoss_command.dgoss_environment}")
            log.debug(f"[bright_black]Executed dgoss command: {' '.join(dgoss_command.command)}")

            image_subdir = results_dir / target.image_name
            image_subdir.mkdir(parents=True, exist_ok=True)
            results_file = image_subdir / f"{target.uid}.json"

            # A spawn failure (e.g. dgoss binary missing) is an execution error, not a test failure.
            if result.exception is not None:
                log.error(f"dgoss for image '{str(target)}' failed to execute: {result.exception}")
                errors.append(
                    BakeryDGossError(
                        f"dgoss execution failed for image '{str(target)}'",
                        "dgoss",
                        cmd=dgoss_command.command,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        parse_error=result.exception,
                        exit_code=result.returncode or 1,
                        metadata={"environment_variables": dgoss_command.dgoss_environment},
                    )
                )
                return

            exit_code = result.returncode

            try:
                output = result.stdout.decode("utf-8").strip()
            except UnicodeDecodeError:
                log.warning(f"Unexpected encoding for dgoss output for image '{str(target)}'.")
                output = result.stdout
            parse_err = None

            try:
                result_data = json.loads(output)
                output = json.dumps(result_data, indent=2)
                report_collection.add_report(target, GossJsonReport(filepath=results_file, **result_data))
            except json.JSONDecodeError as e:
                log.error(f"Failed to decode JSON output from dgoss for image '{str(target)}': {e}")
                parse_err = e
            except pydantic.ValidationError as e:
                log.error(f"Failed to load result data for summary from dgoss for image '{str(target)}: {e}")
                log.warning(f"Test results will be excluded from '{str(target)}' in final summary.")
                parse_err = e

            if not parse_err:
                with open(results_file, "w") as f:
                    log.info(f"Writing results to {results_file}")
                    f.write(output)

            # Goss exits 1 on both test failures and bad configs. Only report an execution error when the exit
            # is non-zero AND we could not parse the output (a genuine failure to run, not a failing test).
            if exit_code != 0 and parse_err is not None:
                log.error(f"dgoss for image '{str(target)}' exited with code {exit_code}")
                errors.append(
                    BakeryDGossError(
                        f"dgoss execution failed for image '{str(target)}'",
                        "dgoss",
                        cmd=dgoss_command.command,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        parse_error=parse_err,
                        exit_code=exit_code,
                        metadata={"environment_variables": dgoss_command.dgoss_environment},
                    )
                )
            elif exit_code == 0:
                log.info(f"[bright_green bold]Goss tests passed for '{str(target)}'")
            else:
                log.warning(f"[yellow bold]Goss tests failed for '{str(target)}'")

        executor = ParallelShellExecutor(max_workers=self.max_workers)
        executor.run(tasks, on_result=handle_result)

        if errors:
            collapsed: BakeryToolRuntimeError | BakeryToolRuntimeErrorGroup | None
            if len(errors) == 1:
                collapsed = errors[0]
            else:
                collapsed = BakeryToolRuntimeErrorGroup("dgoss runtime errors occurred for multiple images.", errors)
        else:
            collapsed = None
        return report_collection, collapsed
