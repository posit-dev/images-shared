import logging
import os
import shutil
import subprocess
from pathlib import Path

from posit_bakery.error import BakeryToolRuntimeError, BakeryToolRuntimeErrorGroup
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.trivy.command import TrivyCommand
from posit_bakery.plugins.builtin.trivy.errors import (
    BakeryTrivyError,
    TRIVY_EXIT_CODE_GENERAL_ERROR,
    TRIVY_EXIT_CODE_SEVERITY_THRESHOLD,
)
from posit_bakery.plugins.builtin.trivy.options import TrivyOptions
from posit_bakery.plugins.builtin.trivy.report import TrivyReportCollection, TrivyScanReport
from posit_bakery.settings import SETTINGS

log = logging.getLogger(__name__)


def _report_breaches_failure_severity(report: TrivyScanReport, failure_severity: list[str]) -> bool:
    """Whether the parsed report contains any finding at one of the given severities.

    Decoupled from trivy's own `--exit-code`, but not from `--severity`: only severities trivy
    scanned appear in the report, which `TrivyCommand` enforces by requiring failureSeverity to
    be a subset of severity. Reads the severity counts already bucketed by `TrivyScanReport`.
    """
    counts = {
        "critical": report.critical_count,
        "high": report.high_count,
        "medium": report.medium_count,
        "low": report.low_count,
        "info": report.info_count,
    }
    return any(counts.get(sev.lower(), 0) > 0 for sev in failure_severity)


class TrivySuite:
    def __init__(
        self,
        context: Path,
        image_targets: list[ImageTarget],
        *,
        tool_options: TrivyOptions | None = None,
        platform: str | None = None,
        severity: list[str] | None = None,
        ignore_unfixed: bool | None = None,
        skip_files: list[str] | None = None,
        skip_dirs: list[str] | None = None,
        exit_code: int | None = None,
        scanners: list[str] | None = None,
        timeout: str | None = None,
        failure_severity: list[str] | None = None,
    ) -> None:
        self.context = context
        self.results_dir = context / "results" / "trivy"

        self.trivy_commands = [
            TrivyCommand.from_image_target(
                target,
                results_dir=self.results_dir,
                tool_options=tool_options,
                platform=platform,
                severity=severity,
                ignore_unfixed=ignore_unfixed,
                skip_files=skip_files,
                skip_dirs=skip_dirs,
                exit_code=exit_code,
                scanners=scanners,
                timeout=timeout,
                failure_severity=failure_severity,
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

            # Ensure output directory exists
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

            # Attempt to parse the SARIF report regardless of exit code: trivy's own
            # `--exit-code` gate returns non-zero on a severity breach even though the scan
            # itself succeeded and wrote a full report, so a parseable report always
            # outranks the raw exit code when deciding whether the scan "worked".
            report = None
            parse_err = None
            if trivy_command.results_file.exists():
                try:
                    report = TrivyScanReport.load(trivy_command.results_file)
                except Exception as e:
                    log.error(f"Failed to parse trivy results for '{str(trivy_command.image_target)}': {e}")
                    parse_err = e

            error_metadata = {"parse_error": str(parse_err)} if parse_err is not None else None

            if report is not None:
                # A report always gets recorded, even when the scan breached a failure
                # threshold: the scan itself succeeded, so the target belongs in the results
                # table with real counts, never a failure verdict.
                report_collection.add_report(trivy_command.image_target, report)

                failure_severity = trivy_command.resolved_failure_severity
                if failure_severity:
                    breached = _report_breaches_failure_severity(report, failure_severity)
                else:
                    # No failureSeverity configured: fall back to trivy's own exit code,
                    # preserving existing behavior for configs that never set the new field.
                    breached = exit_code != 0

                if breached:
                    log.warning(f"[yellow bold]Severity threshold breached for '{str(trivy_command.image_target)}'")
                    errors.append(
                        BakeryTrivyError(
                            f"trivy scan reported a severity threshold breach for '{str(trivy_command.image_target)}'",
                            "trivy",
                            cmd=trivy_command.command,
                            stdout=p.stdout,
                            stderr=p.stderr if verbose else None,
                            exit_code=TRIVY_EXIT_CODE_SEVERITY_THRESHOLD,
                            metadata={"trivy_exit_code": exit_code},
                        )
                    )
                else:
                    log.info(f"[bright_green bold]Scan passed for '{str(trivy_command.image_target)}'")
            else:
                # No parseable report, regardless of exit code: never assert a pass without
                # one, since trivy is installed unpinned and a missing/unreadable results
                # file can also mean its output schema changed underneath us.
                verdict = "NO REPORT" if exit_code == 0 else "SCAN FAILED"
                report_collection.add_failure(trivy_command.image_target, verdict=verdict)

                reason = "results could not be parsed" if parse_err is not None else "no results file was written"
                log.error(f"trivy for '{str(trivy_command.image_target)}' exited with code {exit_code} but {reason}")
                errors.append(
                    BakeryTrivyError(
                        f"trivy scan produced no report for '{str(trivy_command.image_target)}': {reason}",
                        "trivy",
                        cmd=trivy_command.command,
                        stdout=p.stdout,
                        stderr=p.stderr if verbose else None,
                        # The scan produced nothing to substantiate a pass even though trivy
                        # may have exited 0; keep the error's exit code non-zero so callers
                        # keyed on it see a failure, and record what trivy actually returned.
                        exit_code=TRIVY_EXIT_CODE_GENERAL_ERROR,
                        metadata={"trivy_exit_code": exit_code, **(error_metadata or {})},
                    )
                )

        if errors:
            if len(errors) == 1:
                errors = errors[0]
            else:
                errors = BakeryToolRuntimeErrorGroup("trivy runtime errors occurred for multiple images.", errors)
        else:
            errors = None

        return report_collection, errors
