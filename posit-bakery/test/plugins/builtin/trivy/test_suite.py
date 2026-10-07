import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from posit_bakery.targets.selection import select_targets
from posit_bakery.error import BakeryToolRuntimeErrorGroup
from posit_bakery.plugins.builtin.trivy.errors import (
    TRIVY_EXIT_CODE_GENERAL_ERROR,
    TRIVY_EXIT_CODE_SEVERITY_THRESHOLD,
)
from posit_bakery.plugins.builtin.trivy.report import TrivyReportCollection, TrivyScanFailure, TrivyScanReport
from posit_bakery.plugins.builtin.trivy.suite import TrivySuite

pytestmark = [
    pytest.mark.unit,
    pytest.mark.trivy,
]

TRIVY_TESTDATA_DIR = (Path(__file__).parent / "testdata").absolute()
SCAN_RESULT = (TRIVY_TESTDATA_DIR / "scan_result.sarif").read_text()
SUITE_LOGGER = "posit_bakery.plugins.builtin.trivy.suite"

# Number of `runs[].results[]` entries in scan_result.sarif. Every result lands in exactly
# one severity bucket (falling to "info" at worst per Phase 4's bucketing contract), so
# total_count is bucket-agnostic: it holds regardless of the exact CVSS/level thresholds
# Phase 4's TrivyScanReport.load() applies, which this suite-level test never presupposes.
SCAN_RESULT_TOTAL_COUNT = 3


def trivy_stub(returncode: int = 0, results_payload: str | None = None):
    """Return a ``subprocess.run`` stub that mimics the trivy output contract.

    Real trivy writes its SARIF report to the path passed via ``--output``, so the stub
    reproduces that side effect (or omits it, to simulate a scan that never wrote one)
    and the suite parses a real file off disk instead of a mocked report object.
    """

    def _run(cmd, *_args, **_kwargs):
        if results_payload is not None:
            results_file = Path(cmd[cmd.index("--output") + 1])
            results_file.parent.mkdir(parents=True, exist_ok=True)
            results_file.write_text(results_payload)
        completed = MagicMock()
        completed.returncode = returncode
        completed.stdout = b"trivy stdout"
        completed.stderr = b""
        return completed

    return _run


def run_suite(tmpconfig, *, returncode: int = 0, results_payload: str | None = None):
    """Run a TrivySuite over every target in ``tmpconfig`` with a stubbed trivy."""
    suite = TrivySuite(tmpconfig.base_path, select_targets(tmpconfig, tmpconfig.settings))
    with patch(
        f"{SUITE_LOGGER}.subprocess.run",
        side_effect=trivy_stub(returncode, results_payload),
    ):
        return suite.run()


def entries(report_collection: TrivyReportCollection) -> dict:
    """Flatten the collection into ``uid -> report or failure verdict``."""
    return {uid: report for targets in report_collection.values() for uid, (_, report) in targets.items()}


def error_list(errors) -> list:
    """Normalize the suite's error return into a flat list, as the plugin does."""
    if errors is None:
        return []
    if isinstance(errors, BakeryToolRuntimeErrorGroup):
        return list(errors.exceptions)
    return [errors]


class TestTrivySuiteRun:
    def test_exit_zero_with_report_passes(self, get_tmpconfig, caplog):
        """Exit 0 plus a parseable SARIF file is a pass with a real report per target."""
        tmpconfig = get_tmpconfig("basic")
        with caplog.at_level(logging.INFO, logger=SUITE_LOGGER):
            collection, errors = run_suite(tmpconfig, returncode=0, results_payload=SCAN_RESULT)

        assert errors is None
        recorded = entries(collection)
        assert set(recorded) == {target.uid for target in select_targets(tmpconfig, tmpconfig.settings)}
        for report in recorded.values():
            assert isinstance(report, TrivyScanReport)
            assert report.total_count == SCAN_RESULT_TOTAL_COUNT
        assert "Scan passed" in caplog.text

    def test_exit_zero_without_results_file_is_not_a_pass(self, get_tmpconfig, caplog):
        """Exit 0 with no SARIF file must be recorded as a failure, not silently dropped.

        trivy can exit 0 without producing a report (unwritable output path, or an output
        schema change in an unpinned release). Treating that as a pass hides the target
        from the results table while claiming the scan succeeded.
        """
        tmpconfig = get_tmpconfig("basic")
        with caplog.at_level(logging.INFO, logger=SUITE_LOGGER):
            collection, errors = run_suite(tmpconfig, returncode=0, results_payload=None)

        recorded = entries(collection)
        assert set(recorded) == {target.uid for target in select_targets(tmpconfig, tmpconfig.settings)}
        # "NO REPORT" distinguishes a claimed-successful scan with nothing to show for it
        # from a scan that failed outright.
        assert set(recorded.values()) == {TrivyScanFailure(verdict="NO REPORT")}
        assert "Scan passed" not in caplog.text

        errs = error_list(errors)
        assert len(errs) == len(select_targets(tmpconfig, tmpconfig.settings))
        assert {err.exit_code for err in errs} == {TRIVY_EXIT_CODE_GENERAL_ERROR}
        for target in select_targets(tmpconfig, tmpconfig.settings):
            assert any(str(target) in err.message for err in errs)
        for err in errs:
            assert err.metadata["trivy_exit_code"] == 0

    @pytest.mark.parametrize(
        "results_payload",
        ["this is not json", "{}"],
        ids=["invalid_json", "unexpected_schema"],
    )
    def test_exit_zero_with_unparseable_results_file_is_not_a_pass(self, get_tmpconfig, caplog, results_payload):
        """Exit 0 with an unparseable SARIF file is a failure, and says why."""
        tmpconfig = get_tmpconfig("basic")
        with caplog.at_level(logging.INFO, logger=SUITE_LOGGER):
            collection, errors = run_suite(tmpconfig, returncode=0, results_payload=results_payload)

        recorded = entries(collection)
        assert set(recorded) == {target.uid for target in select_targets(tmpconfig, tmpconfig.settings)}
        assert set(recorded.values()) == {TrivyScanFailure(verdict="NO REPORT")}
        assert "Scan passed" not in caplog.text

        errs = error_list(errors)
        assert len(errs) == len(select_targets(tmpconfig, tmpconfig.settings))
        for err in errs:
            assert err.exit_code == TRIVY_EXIT_CODE_GENERAL_ERROR
            assert "parse_error" in str(err)

    def test_nonzero_exit_with_report_still_records_the_report(self, get_tmpconfig, caplog):
        """A non-zero exit with a parseable SARIF report keeps the report (not a failure
        verdict) and raises a severity-threshold error: trivy's own `--exit-code` gate
        returning non-zero means the severity threshold was breached, not that the scan
        itself failed.
        """
        tmpconfig = get_tmpconfig("basic")
        with caplog.at_level(logging.INFO, logger=SUITE_LOGGER):
            collection, errors = run_suite(tmpconfig, returncode=1, results_payload=SCAN_RESULT)

        recorded = entries(collection)
        assert set(recorded) == {target.uid for target in select_targets(tmpconfig, tmpconfig.settings)}
        for report in recorded.values():
            assert isinstance(report, TrivyScanReport)

        errs = error_list(errors)
        assert len(errs) == len(select_targets(tmpconfig, tmpconfig.settings))
        assert {err.exit_code for err in errs} == {TRIVY_EXIT_CODE_SEVERITY_THRESHOLD}
        for err in errs:
            assert err.metadata["trivy_exit_code"] == 1
        assert "Severity threshold breached" in caplog.text
        assert "Scan passed" not in caplog.text

    def test_nonzero_exit_without_results_file_records_failure(self, get_tmpconfig):
        """A non-zero exit with no SARIF file records the target as a failed scan, not a
        severity-threshold breach -- there is no report to substantiate one.
        """
        tmpconfig = get_tmpconfig("basic")
        collection, errors = run_suite(tmpconfig, returncode=1, results_payload=None)

        recorded = entries(collection)
        assert set(recorded) == {target.uid for target in select_targets(tmpconfig, tmpconfig.settings)}
        assert set(recorded.values()) == {TrivyScanFailure(verdict="SCAN FAILED")}

        errs = error_list(errors)
        assert len(errs) == len(select_targets(tmpconfig, tmpconfig.settings))
        assert {err.exit_code for err in errs} == {TRIVY_EXIT_CODE_GENERAL_ERROR}
        for err in errs:
            assert err.metadata["trivy_exit_code"] == 1

    def test_nonzero_exit_with_unparseable_results_file_explains_itself(self, get_tmpconfig):
        """A non-zero exit whose report will not parse reports the parse failure too."""
        tmpconfig = get_tmpconfig("basic")
        collection, errors = run_suite(tmpconfig, returncode=1, results_payload="this is not json")

        recorded = entries(collection)
        assert set(recorded) == {target.uid for target in select_targets(tmpconfig, tmpconfig.settings)}
        assert set(recorded.values()) == {TrivyScanFailure(verdict="SCAN FAILED")}

        errs = error_list(errors)
        assert len(errs) == len(select_targets(tmpconfig, tmpconfig.settings))
        for err in errs:
            assert err.exit_code == TRIVY_EXIT_CODE_GENERAL_ERROR
            assert "parse_error" in str(err)

    def test_results_dir_is_wiped_between_runs(self, get_tmpconfig):
        """results/trivy/ is recreated fresh on each TrivySuite.run(), so a stale report
        from a previous run never leaks into the current one.
        """
        tmpconfig = get_tmpconfig("basic")
        results_dir = tmpconfig.base_path / "results" / "trivy"
        stale_dir = results_dir / "stale-image"
        stale_dir.mkdir(parents=True)
        stale_file = stale_dir / "stale.sarif"
        stale_file.write_text("leftover")

        run_suite(tmpconfig, returncode=0, results_payload=SCAN_RESULT)

        assert not stale_file.exists()

    def test_mixed_batch_returns_error_group_with_matching_exit_codes(self, get_tmpconfig):
        """A batch mixing a severity-breach target and a general-error target returns a
        BakeryToolRuntimeErrorGroup containing exactly those two errors, each carrying its
        distinguishing exit_code (the 'basic' fixture provides exactly 2 targets, so a
        separate passing target is not mixed into this same batch).
        """
        tmpconfig = get_tmpconfig("basic")
        targets = select_targets(tmpconfig, tmpconfig.settings)
        assert len(targets) == 2, "expects the 'basic' fixture's 2 targets (Minimal, Standard)"

        suite = TrivySuite(tmpconfig.base_path, targets)
        outcomes = {
            targets[0].uid: (1, SCAN_RESULT),  # severity breach: report present, nonzero exit
            targets[1].uid: (1, None),  # general error: no report, nonzero exit
        }

        def _run(cmd, *_args, **_kwargs):
            results_file = Path(cmd[cmd.index("--output") + 1])
            returncode, results_payload = outcomes[results_file.stem]
            return trivy_stub(returncode, results_payload)(cmd, *_args, **_kwargs)

        with patch(f"{SUITE_LOGGER}.subprocess.run", side_effect=_run):
            collection, errors = suite.run()

        assert isinstance(errors, BakeryToolRuntimeErrorGroup)
        assert len(errors.exceptions) == 2
        exit_codes = {err.exit_code for err in errors.exceptions}
        assert exit_codes == {TRIVY_EXIT_CODE_SEVERITY_THRESHOLD, TRIVY_EXIT_CODE_GENERAL_ERROR}

        recorded = entries(collection)
        assert isinstance(recorded[targets[0].uid], TrivyScanReport)
        assert recorded[targets[1].uid] == TrivyScanFailure(verdict="SCAN FAILED")


class TestTrivySuiteFailureSeverity:
    def run_with(self, tmpconfig, *, returncode, failure_severity=None):
        suite = TrivySuite(
            tmpconfig.base_path, select_targets(tmpconfig, tmpconfig.settings), failure_severity=failure_severity
        )
        with patch(
            f"{SUITE_LOGGER}.subprocess.run",
            side_effect=trivy_stub(returncode, SCAN_RESULT),
        ):
            return suite.run()

    def test_unset_preserves_exit_code_fallback(self, get_tmpconfig):
        """No failureSeverity: breach follows trivy's own exit code, as before."""
        _, errors = self.run_with(get_tmpconfig("basic"), returncode=1)
        assert {err.exit_code for err in error_list(errors)} == {TRIVY_EXIT_CODE_SEVERITY_THRESHOLD}

    def test_set_ignores_nonzero_exit_when_severity_absent(self, get_tmpconfig, caplog):
        """failureSeverity matching no finding never breaches, even on a nonzero trivy exit."""
        with caplog.at_level(logging.INFO, logger=SUITE_LOGGER):
            _, errors = self.run_with(get_tmpconfig("basic"), returncode=1, failure_severity=["HIGH"])
        assert errors is None
        assert "Scan passed" in caplog.text

    def test_set_breaches_from_report_even_with_zero_exit(self, get_tmpconfig):
        """failureSeverity covering every bucket breaches from report counts alone."""
        _, errors = self.run_with(
            get_tmpconfig("basic"),
            returncode=0,
            failure_severity=["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"],
        )
        assert {err.exit_code for err in error_list(errors)} == {TRIVY_EXIT_CODE_SEVERITY_THRESHOLD}
