import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from posit_bakery.plugins.builtin.wizcli.report import WizScanReport, WizScanReportCollection

pytestmark = [
    pytest.mark.unit,
    pytest.mark.wizcli,
]

WIZCLI_TESTDATA_DIR = (Path(__file__).parent / "testdata").absolute()


class TestWizScanReport:
    def test_load_from_file(self):
        report = WizScanReport.load(WIZCLI_TESTDATA_DIR / "scan_result.json")
        assert report.scan_id == "0069d6c0-7d0b-85d5-9028-affa6e2f8001"
        assert report.status_state == "SUCCESS"
        assert report.status_verdict == "WARN_BY_POLICY"
        assert report.critical_count == 4
        assert report.high_count == 210
        assert report.medium_count == 195
        assert report.low_count == 39
        assert report.info_count == 0

    def test_report_url_non_url_is_none(self):
        """When reportUrl is a descriptive string (not a URL), report_url should be None."""
        report = WizScanReport.load(WIZCLI_TESTDATA_DIR / "scan_result.json")
        assert report.report_url is None

    def test_report_url_real_url(self, tmp_path):
        """When reportUrl is a real URL, report_url should return it."""
        data = json.loads((WIZCLI_TESTDATA_DIR / "scan_result.json").read_text())
        data["reportUrl"] = "https://app.wiz.io/reports/12345"
        result_file = tmp_path / "scan_result.json"
        result_file.write_text(json.dumps(data))
        report = WizScanReport.load(result_file)
        assert report.report_url == "https://app.wiz.io/reports/12345"

    def test_total_vulnerability_count(self):
        report = WizScanReport.load(WIZCLI_TESTDATA_DIR / "scan_result.json")
        assert report.total_count == 4 + 210 + 195 + 39 + 0

    def test_empty_vulnerabilities(self, tmp_path):
        """Report with no vulnerable artifacts should have zero counts."""
        data = json.loads((WIZCLI_TESTDATA_DIR / "scan_result.json").read_text())
        data["result"]["vulnerableSBOMArtifactsByNameVersion"] = []
        result_file = tmp_path / "empty.json"
        result_file.write_text(json.dumps(data))
        report = WizScanReport.load(result_file)
        assert report.critical_count == 0
        assert report.total_count == 0


class TestWizScanReportCollection:
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
        collection = WizScanReportCollection()
        target = self._make_mock_target("connect", "connect-1.0.0-std-ubuntu2204")
        report = WizScanReport.load(WIZCLI_TESTDATA_DIR / "scan_result.json")
        collection.add_report(target, report)

        assert "connect" in collection
        assert "connect-1.0.0-std-ubuntu2204" in collection["connect"]

    def test_aggregate(self):
        collection = WizScanReportCollection()
        target = self._make_mock_target("connect", "connect-1.0.0", "1.0.0", "Standard", "Ubuntu 22.04")
        report = WizScanReport.load(WIZCLI_TESTDATA_DIR / "scan_result.json")
        collection.add_report(target, report)

        agg = collection.aggregate()
        assert agg["total"]["critical"] == 4
        assert agg["total"]["high"] == 210
        assert agg["total"]["medium"] == 195
        assert agg["total"]["low"] == 39
        assert agg["total"]["info"] == 0

    def test_table_returns_rich_table(self):
        collection = WizScanReportCollection()
        target = self._make_mock_target("connect", "connect-1.0.0", "1.0.0", "Standard", "Ubuntu 22.04")
        report = WizScanReport.load(WIZCLI_TESTDATA_DIR / "scan_result.json")
        collection.add_report(target, report)

        table = collection.table()
        assert table.title == "WizCLI Scan Results"
        # Verify column count: Image, Version, Variant, OS, Verdict, Critical, High, Medium, Low, Info, Report URL
        assert len(table.columns) == 11
