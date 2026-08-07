import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from posit_bakery.plugins.builtin.trivy.report import TrivyReport, TrivyReportCollection

pytestmark = [
    pytest.mark.unit,
    pytest.mark.trivy,
]

TRIVY_TESTDATA_DIR = (Path(__file__).parent / "testdata").absolute()


class TestTrivyReport:
    def test_load_from_file(self):
        report = TrivyReport.load(TRIVY_TESTDATA_DIR / "scan_result.sarif")
        assert report.critical_count == 1
        assert report.high_count == 2
        assert report.medium_count == 1
        assert report.low_count == 0
        assert report.unknown_count == 0

    def test_total_vulnerability_count(self):
        report = TrivyReport.load(TRIVY_TESTDATA_DIR / "scan_result.sarif")
        assert report.total_count == 4

    def test_empty_results(self, tmp_path):
        """A SARIF file with no results should have zero counts."""
        data = json.loads((TRIVY_TESTDATA_DIR / "scan_result.sarif").read_text())
        data["runs"][0]["results"] = []
        result_file = tmp_path / "empty.sarif"
        result_file.write_text(json.dumps(data))
        report = TrivyReport.load(result_file)
        assert report.total_count == 0

    def test_unknown_rule_id_counts_as_unknown(self, tmp_path):
        """A result referencing a ruleId with no matching rule counts as UNKNOWN."""
        data = json.loads((TRIVY_TESTDATA_DIR / "scan_result.sarif").read_text())
        data["runs"][0]["results"].append(
            {
                "ruleId": "CVE-NOT-IN-RULES",
                "ruleIndex": 99,
                "level": "note",
                "message": {"text": "orphaned result"},
                "locations": [],
            }
        )
        result_file = tmp_path / "orphan.sarif"
        result_file.write_text(json.dumps(data))
        report = TrivyReport.load(result_file)
        assert report.unknown_count == 1

    @pytest.mark.parametrize(
        "severities,expected",
        [
            (["CRITICAL"], True),
            (["LOW"], False),
            (["LOW", "MEDIUM"], True),
            (["critical"], True),  # case-insensitive
        ],
    )
    def test_breaches(self, severities, expected):
        report = TrivyReport.load(TRIVY_TESTDATA_DIR / "scan_result.sarif")
        assert report.breaches(severities) is expected


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
        report = TrivyReport.load(TRIVY_TESTDATA_DIR / "scan_result.sarif")
        collection.add_report(target, report)

        assert "connect" in collection
        assert "connect-1.0.0-std-ubuntu2204" in collection["connect"]

    def test_aggregate(self):
        collection = TrivyReportCollection()
        target = self._make_mock_target("connect", "connect-1.0.0", "1.0.0", "Standard", "Ubuntu 22.04")
        report = TrivyReport.load(TRIVY_TESTDATA_DIR / "scan_result.sarif")
        collection.add_report(target, report)

        agg = collection.aggregate()
        assert agg["total"]["critical"] == 1
        assert agg["total"]["high"] == 2
        assert agg["total"]["medium"] == 1
        assert agg["total"]["low"] == 0
        assert agg["total"]["unknown"] == 0

    def test_table_returns_rich_table(self):
        collection = TrivyReportCollection()
        target = self._make_mock_target("connect", "connect-1.0.0", "1.0.0", "Standard", "Ubuntu 22.04")
        report = TrivyReport.load(TRIVY_TESTDATA_DIR / "scan_result.sarif")
        collection.add_report(target, report)

        table = collection.table()
        assert table.title == "Trivy Scan Results"
        # Image, Version, Variant, OS, Critical, High, Medium, Low, Unknown
        assert len(table.columns) == 9
