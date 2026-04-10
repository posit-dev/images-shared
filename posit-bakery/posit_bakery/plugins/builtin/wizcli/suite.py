import logging
import os
import shutil
import subprocess
from pathlib import Path

from posit_bakery.error import BakeryToolRuntimeError, BakeryToolRuntimeErrorGroup
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.wizcli.command import WizCLICommand
from posit_bakery.plugins.builtin.wizcli.errors import (
    BakeryWizCLIError,
    WIZCLI_EXIT_CODE_POLICY_VIOLATION,
)
from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions
from posit_bakery.plugins.builtin.wizcli.report import WizScanReport, WizScanReportCollection
from posit_bakery.settings import SETTINGS

log = logging.getLogger(__name__)


class WizCLISuite:
    def __init__(
        self,
        context: Path,
        image_targets: list[ImageTarget],
        *,
        tool_options: WizCLIOptions | None = None,
        disabled_scanners: str | None = None,
        driver: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        use_device_code: bool = False,
        no_browser: bool = False,
        timeout: str | None = None,
        no_publish: bool = False,
        scan_context_id: str | None = None,
        log_file: str | None = None,
    ) -> None:
        self.context = context
        self.results_dir = context / "results" / "wizcli"

        self.wizcli_commands = [
            WizCLICommand.from_image_target(
                target,
                results_dir=self.results_dir,
                tool_options=tool_options,
                disabled_scanners=disabled_scanners,
                driver=driver,
                client_id=client_id,
                client_secret=client_secret,
                use_device_code=use_device_code,
                no_browser=no_browser,
                timeout=timeout,
                no_publish=no_publish,
                scan_context_id=scan_context_id,
                log_file=log_file,
            )
            for target in image_targets
        ]

    def run(self) -> tuple[WizScanReportCollection, BakeryToolRuntimeError | BakeryToolRuntimeErrorGroup | None]:
        if self.results_dir.exists():
            shutil.rmtree(self.results_dir)
        self.results_dir.mkdir(parents=True)

        report_collection = WizScanReportCollection()
        errors = []
        verbose = SETTINGS.log_level == logging.DEBUG

        for wizcli_command in self.wizcli_commands:
            log.info(f"[bright_blue bold]=== Scanning '{str(wizcli_command.image_target)}' with WizCLI ===")
            log.debug(f"[bright_black]Executing wizcli command: {' '.join(wizcli_command.command)}")

            # Ensure output directory exists
            wizcli_command.results_file.parent.mkdir(parents=True, exist_ok=True)

            run_env = os.environ.copy()

            if verbose:
                p = subprocess.run(wizcli_command.command, env=run_env, cwd=self.context, capture_output=True)
                try:
                    stdout_text = p.stdout.decode("utf-8").strip()
                    if stdout_text:
                        log.debug(f"[bright_black]wizcli stdout:\n{stdout_text}")
                except UnicodeDecodeError:
                    pass
                try:
                    stderr_text = p.stderr.decode("utf-8").strip()
                    if stderr_text:
                        log.debug(f"[bright_black]wizcli stderr:\n{stderr_text}")
                except UnicodeDecodeError:
                    pass
            else:
                p = subprocess.run(
                    wizcli_command.command,
                    env=run_env,
                    cwd=self.context,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            exit_code = p.returncode

            # Try to parse the results file written by wizcli
            report = None
            parse_err = None
            if wizcli_command.results_file.exists():
                try:
                    report = WizScanReport.load(wizcli_command.results_file)
                    report_collection.add_report(wizcli_command.image_target, report)
                except Exception as e:
                    log.error(
                        f"Failed to parse wizcli results for '{str(wizcli_command.image_target)}': {e}"
                    )
                    parse_err = e

            # Unlike dgoss (where exit code 1 + valid JSON = test failures, not an error),
            # all non-zero wizcli exit codes are true failures that must be surfaced.
            if exit_code != 0:
                if exit_code == WIZCLI_EXIT_CODE_POLICY_VIOLATION:
                    log.warning(
                        f"[yellow bold]Security policy violation for '{str(wizcli_command.image_target)}'"
                    )
                else:
                    log.error(
                        f"wizcli for '{str(wizcli_command.image_target)}' exited with code {exit_code}"
                    )
                errors.append(
                    BakeryWizCLIError(
                        f"wizcli scan failed for '{str(wizcli_command.image_target)}'",
                        "wizcli",
                        cmd=wizcli_command.command,
                        stdout=p.stdout if verbose else None,
                        stderr=p.stderr if verbose else None,
                        exit_code=exit_code,
                    )
                )
            else:
                log.info(f"[bright_green bold]Scan passed for '{str(wizcli_command.image_target)}'")


        if errors:
            if len(errors) == 1:
                errors = errors[0]
            else:
                errors = BakeryToolRuntimeErrorGroup("wizcli runtime errors occurred for multiple images.", errors)
        else:
            errors = None

        return report_collection, errors
