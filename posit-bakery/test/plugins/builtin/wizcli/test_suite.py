import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from posit_bakery.error import BakeryToolRuntimeErrorGroup
from posit_bakery.plugins.builtin.wizcli.errors import WIZCLI_EXIT_CODE_POLICY_VIOLATION
from posit_bakery.plugins.builtin.wizcli.report import WizScanFailure, WizScanReport, WizScanReportCollection
from posit_bakery.plugins.builtin.wizcli.suite import WizCLISuite

pytestmark = [
    pytest.mark.unit,
    pytest.mark.wizcli,
]

WIZCLI_TESTDATA_DIR = (Path(__file__).parent / "testdata").absolute()
SCAN_RESULT = (WIZCLI_TESTDATA_DIR / "scan_result.json").read_text()
SUITE_LOGGER = "posit_bakery.plugins.builtin.wizcli.suite"


def wizcli_stub(returncode: int = 0, results_payload: str | None = None):
    """Return a ``subprocess.run`` stub that mimics the wizcli output contract.

    Real wizcli writes its report to the path passed via ``--json-output-file``, so the
    stub reproduces that side effect (or omits it, to simulate a scan that never wrote
    one) and the suite parses a real file off disk instead of a mocked report object.
    """

    def _run(cmd, *_args, **_kwargs):
        if results_payload is not None:
            results_file = Path(cmd[cmd.index("--json-output-file") + 1])
            results_file.parent.mkdir(parents=True, exist_ok=True)
            results_file.write_text(results_payload)
        completed = MagicMock()
        completed.returncode = returncode
        completed.stdout = b"wizcli stdout"
        completed.stderr = b""
        return completed

    return _run


def run_suite(tmpconfig, *, returncode: int = 0, results_payload: str | None = None):
    """Run a WizCLISuite over every target in ``tmpconfig`` with a stubbed wizcli."""
    suite = WizCLISuite(tmpconfig.base_path, tmpconfig.targets)
    with patch(
        f"{SUITE_LOGGER}.subprocess.run",
        side_effect=wizcli_stub(returncode, results_payload),
    ):
        return suite.run()


def entries(report_collection: WizScanReportCollection) -> dict:
    """Flatten the collection into ``uid -> report or failure verdict``."""
    return {uid: report for targets in report_collection.values() for uid, (_, report) in targets.items()}


def error_list(errors) -> list:
    """Normalize the suite's error return into a flat list, as the plugin does."""
    if errors is None:
        return []
    if isinstance(errors, BakeryToolRuntimeErrorGroup):
        return list(errors.exceptions)
    return [errors]


class TestWizCLISuiteRun:
    def test_exit_zero_with_report_passes(self, get_tmpconfig, caplog):
        """Exit 0 plus a parseable results file is a pass with a real report per target."""
        tmpconfig = get_tmpconfig("basic")
        with caplog.at_level(logging.INFO, logger=SUITE_LOGGER):
            collection, errors = run_suite(tmpconfig, returncode=0, results_payload=SCAN_RESULT)

        assert errors is None
        recorded = entries(collection)
        assert set(recorded) == {target.uid for target in tmpconfig.targets}
        for report in recorded.values():
            assert isinstance(report, WizScanReport)
            assert report.status_verdict == "WARN_BY_POLICY"
        assert "Scan passed" in caplog.text

    def test_exit_zero_without_results_file_is_not_a_pass(self, get_tmpconfig, caplog):
        """Exit 0 with no results file must be recorded as a failure, not silently dropped.

        wizcli can exit 0 without producing a report (unwritable output path, or an output
        schema change in an unpinned release). Treating that as a pass hides the target from
        the results table while claiming the scan succeeded.
        """
        tmpconfig = get_tmpconfig("basic")
        with caplog.at_level(logging.INFO, logger=SUITE_LOGGER):
            collection, errors = run_suite(tmpconfig, returncode=0, results_payload=None)

        recorded = entries(collection)
        assert set(recorded) == {target.uid for target in tmpconfig.targets}
        # "NO REPORT" distinguishes a claimed-successful scan with nothing to show for it
        # from a scan that failed outright.
        assert set(recorded.values()) == {WizScanFailure(verdict="NO REPORT")}
        assert "Scan passed" not in caplog.text

        # One row per target plus the Total row: the targets stay visible in the table.
        assert collection.table().row_count == len(tmpconfig.targets) + 1

        # Counts are unknown, not zero, so they must not understate the totals.
        assert collection.aggregate()["total"] == {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}

        errs = error_list(errors)
        assert len(errs) == len(tmpconfig.targets)
        # The plugin attributes errors to targets by matching str(target) in the message.
        for target in tmpconfig.targets:
            assert any(str(target) in err.message for err in errs)

    @pytest.mark.parametrize(
        "results_payload",
        ["this is not json", "{}"],
        ids=["invalid_json", "unexpected_schema"],
    )
    def test_exit_zero_with_unparseable_results_file_is_not_a_pass(self, get_tmpconfig, caplog, results_payload):
        """Exit 0 with an unparseable results file is a failure, and says why."""
        tmpconfig = get_tmpconfig("basic")
        with caplog.at_level(logging.INFO, logger=SUITE_LOGGER):
            collection, errors = run_suite(tmpconfig, returncode=0, results_payload=results_payload)

        recorded = entries(collection)
        assert set(recorded) == {target.uid for target in tmpconfig.targets}
        assert set(recorded.values()) == {WizScanFailure(verdict="NO REPORT")}
        assert "Scan passed" not in caplog.text

        errs = error_list(errors)
        assert len(errs) == len(tmpconfig.targets)
        # The parse failure explains itself in the rendered error output.
        for err in errs:
            assert "parse_error" in str(err)

    def test_nonzero_exit_with_report_keeps_the_report(self, get_tmpconfig):
        """A non-zero exit with a parseable report keeps the report and raises an error."""
        tmpconfig = get_tmpconfig("basic")
        collection, errors = run_suite(tmpconfig, returncode=1, results_payload=SCAN_RESULT)

        recorded = entries(collection)
        assert set(recorded) == {target.uid for target in tmpconfig.targets}
        for report in recorded.values():
            assert isinstance(report, WizScanReport)

        errs = error_list(errors)
        assert len(errs) == len(tmpconfig.targets)
        assert {err.exit_code for err in errs} == {1}

    def test_nonzero_exit_without_results_file_records_failure(self, get_tmpconfig):
        """A non-zero exit with no results file records the target as a failed scan."""
        tmpconfig = get_tmpconfig("basic")
        collection, errors = run_suite(tmpconfig, returncode=1, results_payload=None)

        recorded = entries(collection)
        assert set(recorded) == {target.uid for target in tmpconfig.targets}
        assert set(recorded.values()) == {WizScanFailure(verdict="SCAN FAILED")}

        errs = error_list(errors)
        assert len(errs) == len(tmpconfig.targets)
        assert {err.exit_code for err in errs} == {1}

    def test_nonzero_exit_with_unparseable_results_file_explains_itself(self, get_tmpconfig):
        """A non-zero exit whose report will not parse reports the parse failure too."""
        tmpconfig = get_tmpconfig("basic")
        collection, errors = run_suite(tmpconfig, returncode=1, results_payload="this is not json")

        recorded = entries(collection)
        assert set(recorded) == {target.uid for target in tmpconfig.targets}
        assert set(recorded.values()) == {WizScanFailure(verdict="SCAN FAILED")}

        errs = error_list(errors)
        assert len(errs) == len(tmpconfig.targets)
        for err in errs:
            assert err.exit_code == 1
            assert "parse_error" in str(err)

    def test_policy_violation_warns_and_records_report(self, get_tmpconfig, caplog):
        """A policy violation warns instead of erroring in the log, and stays recorded."""
        tmpconfig = get_tmpconfig("basic")
        with caplog.at_level(logging.INFO, logger=SUITE_LOGGER):
            collection, errors = run_suite(
                tmpconfig,
                returncode=WIZCLI_EXIT_CODE_POLICY_VIOLATION,
                results_payload=SCAN_RESULT,
            )

        recorded = entries(collection)
        assert set(recorded) == {target.uid for target in tmpconfig.targets}
        for report in recorded.values():
            assert isinstance(report, WizScanReport)

        errs = error_list(errors)
        assert len(errs) == len(tmpconfig.targets)
        assert {err.exit_code for err in errs} == {WIZCLI_EXIT_CODE_POLICY_VIOLATION}

        assert "Security policy violation" in caplog.text
        assert "exited with code" not in caplog.text
        assert logging.ERROR not in {record.levelno for record in caplog.records if record.name == SUITE_LOGGER}
