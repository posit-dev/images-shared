import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from posit_bakery.plugins.builtin.trivy.report import TrivyReportCollection, TrivyScanFailure, TrivyScanReport

pytestmark = [
    pytest.mark.unit,
    pytest.mark.trivy,
]

TRIVY_TESTDATA_DIR = (Path(__file__).parent / "testdata").absolute()


def _sarif(runs: list[dict]) -> dict:
    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": runs,
    }


class TestTrivyScanReport:
    def test_load_from_file(self):
        """`scan_result.sarif` (Phase 3's shared fixture) carries three results: one bucketed
        via severity tag (critical), one via `defaultConfiguration.level` fallback
        (medium), and one with an unresolvable `ruleId` (info)."""
        report = TrivyScanReport.load(TRIVY_TESTDATA_DIR / "scan_result.sarif")
        assert report.critical_count == 1
        assert report.high_count == 0
        assert report.medium_count == 1
        assert report.low_count == 0
        assert report.info_count == 1

    def test_tag_bucketing_wins_over_level(self):
        """CVE-2024-0001 carries a `CRITICAL` tag and `level: error`; the tag must win
        (level alone would bucket as high)."""
        report = TrivyScanReport.load(TRIVY_TESTDATA_DIR / "scan_result.sarif")
        assert report.critical_count == 1
        assert report.high_count == 0

    def test_level_fallback_when_no_tag(self):
        """CVE-2024-0002 carries no severity tag; its `defaultConfiguration.level:
        warning` falls back to the medium bucket."""
        report = TrivyScanReport.load(TRIVY_TESTDATA_DIR / "scan_result.sarif")
        assert report.medium_count == 1

    def test_unresolvable_rule_id_buckets_as_info(self):
        """CVE-2024-9999 matches no entry in `runs[].tool.driver.rules[]`; it has no
        metadata to bucket against, so it is counted as info rather than dropped."""
        report = TrivyScanReport.load(TRIVY_TESTDATA_DIR / "scan_result.sarif")
        assert report.info_count == 1

    def test_total_vulnerability_count(self):
        report = TrivyScanReport.load(TRIVY_TESTDATA_DIR / "scan_result.sarif")
        assert report.total_count == 3

    def test_rewrites_minified_file_with_indentation(self):
        """A minified SARIF file is rewritten with `indent=2` and a trailing newline; a
        second `load()` of the now-formatted file must be byte-identical (no ping-pong)."""
        raw = (TRIVY_TESTDATA_DIR / "scan_result.sarif").read_text()
        result_file_dir = TRIVY_TESTDATA_DIR.parent / "_tmp_rewrite_check"
        result_file_dir.mkdir(exist_ok=True)
        result_file = result_file_dir / "minified.sarif"
        try:
            result_file.write_text(raw)
            TrivyScanReport.load(result_file)
            formatted_once = result_file.read_text()
            assert formatted_once == json.dumps(json.loads(raw), indent=2) + "\n"

            TrivyScanReport.load(result_file)
            formatted_twice = result_file.read_text()
            assert formatted_twice == formatted_once
        finally:
            result_file.unlink(missing_ok=True)
            result_file_dir.rmdir()

    def test_empty_results(self, tmp_path):
        """A run with no results has zero counts across every severity bucket."""
        data = _sarif([{"tool": {"driver": {"name": "Trivy", "rules": []}}, "results": []}])
        result_file = tmp_path / "empty.sarif"
        result_file.write_text(json.dumps(data))

        report = TrivyScanReport.load(result_file)
        assert report.total_count == 0
        assert report.critical_count == 0

    def test_low_and_info_level_fallbacks(self, tmp_path):
        """`level: note` falls back to low and `level: none` falls back to info, rounding
        out the `defaultConfiguration.level` fallback mapping that the shared fixture does
        not itself exercise (it only carries `error`/`warning`)."""
        data = _sarif(
            [
                {
                    "tool": {
                        "driver": {
                            "name": "Trivy",
                            "rules": [
                                {"id": "R1", "defaultConfiguration": {"level": "note"}},
                                {"id": "R2", "defaultConfiguration": {"level": "none"}},
                            ],
                        }
                    },
                    "results": [
                        {"ruleId": "R1", "level": "note"},
                        {"ruleId": "R2", "level": "none"},
                    ],
                }
            ]
        )
        result_file = tmp_path / "levels.sarif"
        result_file.write_text(json.dumps(data))

        report = TrivyScanReport.load(result_file)
        assert report.low_count == 1
        assert report.info_count == 1

    def test_label_wins_over_cvss_score(self, tmp_path):
        """A rule labelled LOW with a 9.8 CVSS score counts as low, not critical."""
        data = _sarif(
            [
                {
                    "tool": {
                        "driver": {
                            "name": "Trivy",
                            "rules": [
                                {
                                    "id": "R1",
                                    "properties": {"security-severity": "9.8", "tags": ["vulnerability", "LOW"]},
                                    "defaultConfiguration": {"level": "note"},
                                }
                            ],
                        }
                    },
                    "results": [{"ruleId": "R1", "level": "note"}],
                }
            ]
        )
        result_file = tmp_path / "low_cvss.sarif"
        result_file.write_text(json.dumps(data))

        report = TrivyScanReport.load(result_file)
        assert report.low_count == 1
        assert report.critical_count == 0

    def test_unknown_tag_buckets_as_info(self, tmp_path):
        """trivy's `UNKNOWN` label maps to the info bucket."""
        data = _sarif(
            [
                {
                    "tool": {
                        "driver": {
                            "name": "Trivy",
                            "rules": [{"id": "R1", "properties": {"tags": ["UNKNOWN"]}}],
                        }
                    },
                    "results": [{"ruleId": "R1", "level": "note"}],
                }
            ]
        )
        result_file = tmp_path / "unknown.sarif"
        result_file.write_text(json.dumps(data))

        report = TrivyScanReport.load(result_file)
        assert report.info_count == 1
        assert report.low_count == 0


class TestTrivyReportCollection:
    def _make_mock_target(self, image_name, uid, version="1.0.0", variant=None, os_name=None):
        target = MagicMock()
        target.image_name = image_name
        target.uid = uid
        target.image_version.name = version
        target.image_variant = None
        target.image_os = None
        if variant:
            target.image_variant = MagicMock()
            target.image_variant.name = variant
        if os_name:
            target.image_os = MagicMock()
            target.image_os.name = os_name
        return target

    def test_add_report(self):
        collection = TrivyReportCollection()
        target = self._make_mock_target("connect", "connect-1.0.0-std-ubuntu2204")
        report = TrivyScanReport.load(TRIVY_TESTDATA_DIR / "scan_result.sarif")
        collection.add_report(target, report)

        assert "connect" in collection
        assert "connect-1.0.0-std-ubuntu2204" in collection["connect"]

    def test_aggregate(self):
        collection = TrivyReportCollection()
        target = self._make_mock_target("connect", "connect-1.0.0", "1.0.0", "Standard", "Ubuntu 22.04")
        report = TrivyScanReport.load(TRIVY_TESTDATA_DIR / "scan_result.sarif")
        collection.add_report(target, report)

        agg = collection.aggregate()
        assert agg["total"]["critical"] == 1
        assert agg["total"]["medium"] == 1
        assert agg["total"]["info"] == 1

    def test_add_failure_appears_in_aggregate(self):
        """Failed scans keep a row with unknown counts so the table shows real coverage."""
        collection = TrivyReportCollection()
        target = self._make_mock_target("connect", "connect-1.0.0", "1.0.0", "Standard", "Ubuntu 22.04")
        collection.add_failure(target)

        agg = collection.aggregate()
        row = agg["connect"]["1.0.0"]["Ubuntu 22.04"]["Standard"]
        assert row["status"] == "SCAN FAILED"
        assert row["critical"] is None

    def test_add_failure_excluded_from_totals(self):
        """A failed scan must not contribute zeros that understate the totals."""
        collection = TrivyReportCollection()
        ok_target = self._make_mock_target("connect", "connect-1.0.0", "1.0.0", "Standard", "Ubuntu 22.04")
        failed_target = self._make_mock_target("connect", "connect-1.0.0-min", "1.0.0", "Minimal", "Ubuntu 22.04")
        collection.add_report(ok_target, TrivyScanReport.load(TRIVY_TESTDATA_DIR / "scan_result.sarif"))
        collection.add_failure(failed_target)

        agg = collection.aggregate()
        assert agg["total"]["critical"] == 1
        assert agg["total"]["info"] == 1

    def test_table_renders_failed_rows(self):
        """The results table includes failed targets rather than silently dropping them."""
        collection = TrivyReportCollection()
        ok_target = self._make_mock_target("connect", "connect-1.0.0", "1.0.0", "Standard", "Ubuntu 22.04")
        failed_target = self._make_mock_target("connect", "connect-1.0.0-min", "1.0.0", "Minimal", "Ubuntu 22.04")
        collection.add_report(ok_target, TrivyScanReport.load(TRIVY_TESTDATA_DIR / "scan_result.sarif"))
        collection.add_failure(failed_target)

        table = collection.table()
        # Two target rows plus the Total row.
        assert table.row_count == 3

    def test_table_returns_rich_table(self):
        collection = TrivyReportCollection()
        target = self._make_mock_target("connect", "connect-1.0.0", "1.0.0", "Standard", "Ubuntu 22.04")
        report = TrivyScanReport.load(TRIVY_TESTDATA_DIR / "scan_result.sarif")
        collection.add_report(target, report)

        table = collection.table()
        assert table.title == "Trivy Scan Results"
        # Verify column count: Image, Version, Variant, OS, Status, Critical, High, Medium, Low, Info
        assert len(table.columns) == 10

    def test_add_failure_returns_typed_failure(self):
        """`add_failure` stores a `TrivyScanFailure`, not a bare string, so callers can
        distinguish a failed scan from a real report by type."""
        collection = TrivyReportCollection()
        target = self._make_mock_target("connect", "connect-1.0.0")
        collection.add_failure(target, verdict="NO REPORT")

        _, stored = collection["connect"]["connect-1.0.0"]
        assert isinstance(stored, TrivyScanFailure)
        assert stored.verdict == "NO REPORT"
