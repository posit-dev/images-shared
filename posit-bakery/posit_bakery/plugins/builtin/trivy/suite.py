import logging
import os
import shutil
import subprocess
from pathlib import Path

from posit_bakery.error import BakeryToolRuntimeError, BakeryToolRuntimeErrorGroup
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.trivy.command import TrivyCommand
from posit_bakery.plugins.builtin.trivy.errors import BakeryTrivyError
from posit_bakery.plugins.builtin.trivy.report import TrivyReport, TrivyReportCollection
from posit_bakery.settings import SETTINGS

log = logging.getLogger(__name__)


class TrivySuite:
    def __init__(
        self,
        context: Path,
        image_targets: list[ImageTarget],
        *,
        severity: str | None = None,
        disabled_scanners: str | None = None,
        timeout: str | None = None,
        trivy_config: Path | None = None,
    ) -> None:
        self.context = context
        self.results_dir = context / "results" / "trivy"

        self.trivy_commands = [
            TrivyCommand.from_image_target(
                target,
                results_dir=self.results_dir,
                severity=severity,
                disabled_scanners=disabled_scanners,
                timeout=timeout,
                trivy_config=trivy_config,
            )
            for target in image_targets
        ]

    def run(self) -> tuple[TrivyReportCollection, BakeryToolRuntimeError | BakeryToolRuntimeErrorGroup | None]:
        if self.results_dir.exists():
            shutil.rmtree(self.results_dir)
        self.results_dir.mkdir(parents=True)

        report_collection = TrivyReportCollection()
        errors = []
        verbose = SETTINGS.log_level == logging.DEBUG

        for trivy_command in self.trivy_commands:
            log.info(f"[bright_blue bold]=== Scanning '{str(trivy_command.image_target)}' with Trivy ===")
            log.debug(f"[bright_black]Executing trivy command: {' '.join(trivy_command.command)}")

            trivy_command.results_file.parent.mkdir(parents=True, exist_ok=True)

            run_env = os.environ.copy()

            p = subprocess.run(
                trivy_command.command,
                env=run_env,
                cwd=self.context,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE if verbose else subprocess.DEVNULL,
            )

            if verbose:
                try:
                    stderr_text = p.stderr.decode("utf-8").strip()
                    if stderr_text:
                        log.debug(f"[bright_black]trivy stderr:\n{stderr_text}")
                except UnicodeDecodeError:
                    pass

            exit_code = p.returncode

            report = None
            if exit_code == 0:
                if trivy_command.results_file.exists():
                    try:
                        report = TrivyReport.load(trivy_command.results_file)
                        report_collection.add_report(trivy_command.image_target, report)
                    except Exception as e:
                        log.error(f"Failed to parse trivy results for '{str(trivy_command.image_target)}': {e}")
                        exit_code = 1
                else:
                    log.error(f"trivy for '{str(trivy_command.image_target)}' exited 0 but produced no results file")
                    exit_code = 1

            # trivy's own --exit-code flag is never set (see TrivyCommand), so any
            # non-zero exit here is a true execution failure, never "found vulnerabilities."
            if exit_code != 0:
                log.error(f"trivy for '{str(trivy_command.image_target)}' exited with code {exit_code}")
                errors.append(
                    BakeryTrivyError(
                        f"trivy scan failed for '{str(trivy_command.image_target)}'",
                        "trivy",
                        cmd=trivy_command.command,
                        stdout=p.stdout,
                        stderr=p.stderr if verbose else None,
                        exit_code=exit_code,
                    )
                )
            else:
                log.info(f"[bright_green bold]Scan completed for '{str(trivy_command.image_target)}'")

        if errors:
            if len(errors) == 1:
                errors = errors[0]
            else:
                errors = BakeryToolRuntimeErrorGroup("trivy runtime errors occurred for multiple images.", errors)
        else:
            errors = None

        return report_collection, errors
