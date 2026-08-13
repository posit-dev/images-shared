import logging
import os
import shutil
import subprocess
from pathlib import Path

from posit_bakery.error import BakeryToolRuntimeError, BakeryToolRuntimeErrorGroup
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.wizcli.command import WizCLICommand, WizCLIDriverEnum
from posit_bakery.plugins.builtin.wizcli.errors import (
    BakeryWizCLIError,
    WIZCLI_EXIT_CODE_GENERAL_ERROR,
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
        platform: str | None = None,
        disabled_scanners: str | None = None,
        driver: WizCLIDriverEnum = WizCLIDriverEnum.EXTRACT,
        policies: str | None = None,
        projects: str | None = None,
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
                platform=platform,
                disabled_scanners=disabled_scanners,
                driver=driver,
                policies=policies,
                projects=projects,
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

            # wizcli sends primary error/success messages to stdout and verbose logging
            # clutter to stderr. Always capture stdout for error reporting on failure;
            # suppress stderr unless verbose mode is active.
            p = subprocess.run(
                wizcli_command.command,
                env=run_env,
                cwd=self.context,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE if verbose else subprocess.DEVNULL,
            )

            if verbose:
                try:
                    stderr_text = p.stderr.decode("utf-8").strip()
                    if stderr_text:
                        log.debug(f"[bright_black]wizcli stderr:\n{stderr_text}")
                except UnicodeDecodeError:
                    pass

            exit_code = p.returncode

            # Try to parse the results file written by wizcli
            report = None
            parse_err = None
            if wizcli_command.results_file.exists():
                try:
                    report = WizScanReport.load(wizcli_command.results_file)
                except Exception as e:
                    log.error(f"Failed to parse wizcli results for '{str(wizcli_command.image_target)}': {e}")
                    parse_err = e

            # Record every target exactly once, independent of the exit code. A target that
            # reaches neither add_report nor add_failure vanishes from the results table,
            # which would look complete while covering only the targets that happened to scan.
            if report is not None:
                report_collection.add_report(wizcli_command.image_target, report)
            else:
                # Exit 0 without a report is not a pass, so give it its own verdict: wizcli
                # claimed success but left nothing to substantiate it.
                verdict = "NO REPORT" if exit_code == 0 else "SCAN FAILED"
                report_collection.add_failure(wizcli_command.image_target, verdict=verdict)

            # A parse failure is the most useful detail for diagnosing a missing report, so
            # carry it into the error output rather than leaving it only in the log.
            error_metadata = {"parse_error": str(parse_err)} if parse_err is not None else None

            # Unlike dgoss (where exit code 1 + valid JSON = test failures, not an error),
            # all non-zero wizcli exit codes are true failures that must be surfaced.
            if exit_code != 0:
                if exit_code == WIZCLI_EXIT_CODE_POLICY_VIOLATION:
                    log.warning(f"[yellow bold]Security policy violation for '{str(wizcli_command.image_target)}'")
                else:
                    log.error(f"wizcli for '{str(wizcli_command.image_target)}' exited with code {exit_code}")
                errors.append(
                    BakeryWizCLIError(
                        f"wizcli scan failed for '{str(wizcli_command.image_target)}'",
                        "wizcli",
                        cmd=wizcli_command.command,
                        stdout=p.stdout,
                        stderr=p.stderr if verbose else None,
                        exit_code=exit_code,
                        metadata=error_metadata,
                    )
                )
            elif report is None:
                # Never assert a pass without a report: wizcli is installed unpinned, so a
                # missing or unreadable results file can also mean its output schema changed.
                reason = "results could not be parsed" if parse_err is not None else "no results file was written"
                log.error(f"wizcli for '{str(wizcli_command.image_target)}' exited with code {exit_code} but {reason}")
                errors.append(
                    BakeryWizCLIError(
                        f"wizcli scan produced no report for '{str(wizcli_command.image_target)}': {reason}",
                        "wizcli",
                        cmd=wizcli_command.command,
                        stdout=p.stdout,
                        stderr=p.stderr if verbose else None,
                        # The scan itself failed even though wizcli reported success; keep the
                        # error's exit code non-zero so callers keyed on it see a failure, and
                        # record what wizcli actually returned in the metadata.
                        exit_code=WIZCLI_EXIT_CODE_GENERAL_ERROR,
                        metadata={"wizcli_exit_code": exit_code, **(error_metadata or {})},
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
