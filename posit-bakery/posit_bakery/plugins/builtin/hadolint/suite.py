import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

from posit_bakery.error import BakeryToolRuntimeError, BakeryToolRuntimeErrorGroup
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.hadolint.command import HadolintCommand
from posit_bakery.plugins.builtin.hadolint.errors import BakeryHadolintError
from posit_bakery.plugins.builtin.hadolint.options import HadolintOptions
from posit_bakery.plugins.builtin.hadolint.report import HadolintReport, HadolintReportCollection

log = logging.getLogger(__name__)


class HadolintSuite:
    def __init__(
        self,
        context: Path,
        image_targets: list[ImageTarget],
        options_override: HadolintOptions | None = None,
    ) -> None:
        self.context = context
        self.image_targets = image_targets
        self.hadolint_commands = [
            HadolintCommand.from_image_target(target, options_override=options_override)
            for target in image_targets
        ]

    def run(self) -> tuple[HadolintReportCollection, BakeryToolRuntimeError | BakeryToolRuntimeErrorGroup | None]:
        results_dir = self.context / "results" / "hadolint"
        if results_dir.exists():
            shutil.rmtree(results_dir)
        results_dir.mkdir(parents=True)

        report_collection = HadolintReportCollection()
        errors = []

        for hadolint_command in self.hadolint_commands:
            target = hadolint_command.image_target
            log.info(f"[bright_blue bold]=== Running hadolint for '{str(target)}' ===")
            log.debug(f"[bright_black]Executing hadolint command: {' '.join(hadolint_command.command)}")

            run_env = os.environ.copy()
            p = subprocess.run(hadolint_command.command, env=run_env, capture_output=True)
            exit_code = p.returncode

            image_subdir = results_dir / target.image_name
            image_subdir.mkdir(parents=True, exist_ok=True)
            results_file = image_subdir / f"{target.uid}.json"

            try:
                output = p.stdout.decode("utf-8").strip()
            except UnicodeDecodeError:
                log.warning(f"Unexpected encoding for hadolint output for image '{str(target)}'.")
                output = p.stdout

            parse_err = None
            try:
                result_data = json.loads(output)
                output = json.dumps(result_data, indent=2)
                report_collection.add_report(
                    target,
                    HadolintReport(
                        filepath=results_file,
                        containerfile=target.containerfile,
                        results=result_data,
                    ),
                )
            except json.JSONDecodeError as e:
                log.error(f"Failed to decode JSON output from hadolint for image '{str(target)}': {e}")
                parse_err = e

            if not parse_err:
                with open(results_file, "w") as f:
                    log.info(f"Writing results to {results_file}")
                    f.write(output)

            if exit_code != 0 and parse_err is not None:
                log.error(f"hadolint for image '{str(target)}' exited with code {exit_code}")
                errors.append(
                    BakeryHadolintError(
                        f"hadolint execution failed for image '{str(target)}'",
                        "hadolint",
                        cmd=hadolint_command.command,
                        stdout=p.stdout,
                        stderr=p.stderr,
                        parse_error=parse_err,
                        exit_code=exit_code,
                    )
                )
            elif exit_code == 0:
                log.info(f"[bright_green bold]hadolint passed for '{str(target)}'")
            else:
                log.warning(f"[yellow bold]hadolint found issues for '{str(target)}'")

        if errors:
            if len(errors) == 1:
                errors = errors[0]
            else:
                errors = BakeryToolRuntimeErrorGroup("hadolint runtime errors occurred for multiple images.", errors)
        else:
            errors = None
        return report_collection, errors
