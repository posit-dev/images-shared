import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from posit_bakery.plugins.builtin.hadolint.report import (
    HadolintResult,
    HadolintReport,
    HadolintReportCollection,
)
from posit_bakery.image.image_target import ImageTarget

pytestmark = [pytest.mark.unit, pytest.mark.hadolint]


@pytest.fixture
def sample_results_data():
    """Sample hadolint JSON output as a list of dicts."""
    return [
        {
            "code": "DL3007",
            "column": 1,
            "file": "Containerfile",
            "level": "warning",
            "line": 1,
            "message": "Using latest is prone to errors",
        },
        {
            "code": "DL3008",
            "column": 1,
            "file": "Containerfile",
            "level": "warning",
            "line": 5,
            "message": "Pin versions in apt get install",
        },
        {
            "code": "DL3009",
            "column": 1,
            "file": "Containerfile",
            "level": "info",
            "line": 5,
            "message": "Delete the apt lists after installing",
        },
    ]


class TestHadolintResult:
    def test_parse_result(self):
        result = HadolintResult(
            code="DL3008",
            column=1,
            file="Containerfile",
            level="warning",
            line=10,
            message="Pin versions in apt get install",
        )
        assert result.code == "DL3008"
        assert result.level == "warning"
        assert result.line == 10

    def test_parse_from_dict(self):
        data = {"code": "DL3007", "column": 1, "file": "-", "level": "error", "line": 1, "message": "Using latest"}
        result = HadolintResult.model_validate(data)
        assert result.code == "DL3007"
        assert result.level == "error"


class TestHadolintReport:
    def test_create_report(self, sample_results_data):
        report = HadolintReport(
            containerfile=Path("test-image/1.0.0/Containerfile.ubuntu2204.std"),
            results=[HadolintResult.model_validate(r) for r in sample_results_data],
        )
        assert report.total_count == 3
        assert report.warning_count == 2
        assert report.info_count == 1
        assert report.error_count == 0
        assert report.style_count == 0

    def test_empty_report(self):
        report = HadolintReport(
            containerfile=Path("Containerfile"),
            results=[],
        )
        assert report.total_count == 0
        assert report.error_count == 0

    def test_load_from_file(self, tmp_path, sample_results_data):
        report_file = tmp_path / "results.json"
        report_file.write_text(json.dumps(sample_results_data))
        report = HadolintReport.load(report_file, containerfile=Path("Containerfile"))
        assert report.total_count == 3
        assert report.filepath == report_file

    def test_errors_property(self, sample_results_data):
        report = HadolintReport(
            containerfile=Path("Containerfile"),
            results=[HadolintResult.model_validate(r) for r in sample_results_data],
        )
        assert len(report.errors) == 0

    def test_warnings_property(self, sample_results_data):
        report = HadolintReport(
            containerfile=Path("Containerfile"),
            results=[HadolintResult.model_validate(r) for r in sample_results_data],
        )
        assert len(report.warnings) == 2
        assert all(r.level == "warning" for r in report.warnings)

    def test_by_level(self, sample_results_data):
        report = HadolintReport(
            containerfile=Path("Containerfile"),
            results=[HadolintResult.model_validate(r) for r in sample_results_data],
        )
        warnings = report.by_level("warning")
        assert len(warnings) == 2
        infos = report.by_level("info")
        assert len(infos) == 1
        errors = report.by_level("error")
        assert len(errors) == 0


class TestHadolintReportCollection:
    @pytest.fixture
    def mock_target(self):
        target = MagicMock(spec=ImageTarget)
        target.image_name = "test-image"
        target.uid = "test-image-1.0.0-ubuntu2204-standard"
        target.image_version = MagicMock()
        target.image_version.name = "1.0.0"
        target.image_variant = MagicMock()
        target.image_variant.name = "Standard"
        target.image_os = MagicMock()
        target.image_os.name = "ubuntu2204"
        return target

    @pytest.fixture
    def report_with_issues(self, sample_results_data):
        return HadolintReport(
            containerfile=Path("test-image/1.0.0/Containerfile.ubuntu2204.std"),
            results=[HadolintResult.model_validate(r) for r in sample_results_data],
        )

    def test_add_report(self, mock_target, report_with_issues):
        collection = HadolintReportCollection()
        collection.add_report(mock_target, report_with_issues)
        assert "test-image" in collection
        assert mock_target.uid in collection["test-image"]

    def test_add_multiple_reports(self, report_with_issues):
        collection = HadolintReportCollection()

        target1 = MagicMock(spec=ImageTarget)
        target1.image_name = "image-a"
        target1.uid = "image-a-1.0.0"

        target2 = MagicMock(spec=ImageTarget)
        target2.image_name = "image-a"
        target2.uid = "image-a-2.0.0"

        target3 = MagicMock(spec=ImageTarget)
        target3.image_name = "image-b"
        target3.uid = "image-b-1.0.0"

        collection.add_report(target1, report_with_issues)
        collection.add_report(target2, report_with_issues)
        collection.add_report(target3, report_with_issues)

        assert len(collection) == 2
        assert len(collection["image-a"]) == 2
        assert len(collection["image-b"]) == 1

    def test_has_issues(self, mock_target, report_with_issues):
        collection = HadolintReportCollection()
        collection.add_report(mock_target, report_with_issues)
        assert collection.has_issues is True

    def test_no_issues(self, mock_target):
        collection = HadolintReportCollection()
        empty_report = HadolintReport(containerfile=Path("Containerfile"), results=[])
        collection.add_report(mock_target, empty_report)
        assert collection.has_issues is False

    def test_empty_collection(self):
        collection = HadolintReportCollection()
        assert collection.has_issues is False

    def test_table_generation(self, mock_target, report_with_issues):
        collection = HadolintReportCollection()
        collection.add_report(mock_target, report_with_issues)
        table = collection.table()
        assert table.title == "Hadolint Results"
        column_names = [col.header for col in table.columns]
        assert "Image Name" in column_names
        assert "Containerfile" in column_names
        assert "Errors" in column_names
        assert "Warnings" in column_names

    def test_empty_collection_table(self):
        collection = HadolintReportCollection()
        table = collection.table()
        assert table.title == "Hadolint Results"

    def test_issues_by_level_warning(self, mock_target, report_with_issues):
        """Test issues_by_level returns warnings and errors when threshold is warning."""
        collection = HadolintReportCollection()
        collection.add_report(mock_target, report_with_issues)
        issues = collection.issues_by_level("warning")
        assert mock_target.uid in issues
        assert len(issues[mock_target.uid]) == 2  # 2 warnings, 0 errors
        assert all(r.level in ("error", "warning") for r in issues[mock_target.uid])

    def test_issues_by_level_error(self, mock_target, report_with_issues):
        """Test issues_by_level returns only errors when threshold is error."""
        collection = HadolintReportCollection()
        collection.add_report(mock_target, report_with_issues)
        issues = collection.issues_by_level("error")
        assert issues == {}  # No errors in sample data

    def test_issues_by_level_style(self, mock_target, report_with_issues):
        """Test issues_by_level returns all levels when threshold is style."""
        collection = HadolintReportCollection()
        collection.add_report(mock_target, report_with_issues)
        issues = collection.issues_by_level("style")
        assert mock_target.uid in issues
        assert len(issues[mock_target.uid]) == 3  # 2 warnings + 1 info
