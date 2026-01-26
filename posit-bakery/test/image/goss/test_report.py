"""Tests for posit_bakery.image.goss.report module.

Tests cover the Goss report parsing and aggregation functionality.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from posit_bakery.image.goss.report import (
    GossMatcherResult,
    GossResult,
    GossSummary,
    GossJsonReport,
    GossJsonReportCollection,
)
from posit_bakery.image.image_target import ImageTarget


pytestmark = [pytest.mark.unit, pytest.mark.goss]


@pytest.fixture
def passing_command_result_data():
    """Sample data for a passing command Goss test result."""
    return {
        "successful": True,
        "skipped": False,
        "err": None,
        "result": 0,
        "resource-id": "python --version",
        "resource-type": "command",
        "property": "exit-status",
        "title": "Python version check",
        "summary-line": "Command: python --version: exit-status: matches expectation: 0",
        "summary-line-compact": "python --version exit-status",
        "duration": 1500000,  # 1.5ms in nanoseconds
        "start-time": "2025-01-01T00:00:00Z",
        "end-time": "2025-01-01T00:00:00.0015Z",
        "matcher-result": {
            "message": "matches expectation",
            "expected": 0,
            "actual": 0,
        },
    }


@pytest.fixture
def failed_command_result_data():
    """Sample data for a failed command Goss test result."""
    return {
        "successful": False,
        "skipped": False,
        "err": None,
        "result": 1,
        "resource-id": "missing-cmd",
        "resource-type": "command",
        "property": "exit-status",
        "title": "Missing command check",
        "summary-line": "Command: missing-cmd: exit-status: does not match: expected 0, got 127",
        "summary-line-compact": "missing-cmd exit-status",
        "duration": 500000,
        "start-time": "2025-01-01T00:00:01Z",
        "end-time": "2025-01-01T00:00:01.0005Z",
        "matcher-result": {
            "message": "does not match",
            "expected": 0,
            "actual": 127,
        },
    }


@pytest.fixture
def skipped_command_result_data():
    """Sample data for a skipped command Goss test result."""
    return {
        "successful": False,
        "skipped": True,
        "err": None,
        "result": 0,
        "resource-id": "optional-feature",
        "resource-type": "command",
        "property": "exit-status",
        "title": "Optional feature",
        "summary-line": "Command: optional-feature: skipped",
        "summary-line-compact": "optional-feature",
        "duration": 0,
        "start-time": "2025-01-01T00:00:02Z",
        "end-time": "2025-01-01T00:00:02Z",
        "matcher-result": {
            "message": "skipped",
        },
    }


class TestGossMatcherResult:
    def test_basic_matcher_result(self):
        """Test creating a basic matcher result."""
        result = GossMatcherResult(
            message="matches expectation",
            expected=0,
            actual=0,
        )
        assert result.message == "matches expectation"
        assert result.expected == 0
        assert result.actual == 0

    def test_matcher_result_with_elements(self):
        """Test matcher result with extra/found/missing elements."""
        result = GossMatcherResult(
            message="partial match",
            expected=["a", "b", "c"],
            actual=["a", "b"],
            **{
                "extra-elements": [],
                "found-elements": ["a", "b"],
                "missing-elements": ["c"],
            }
        )
        assert result.missing_elements == ["c"]
        assert result.found_elements == ["a", "b"]

    def test_matcher_result_defaults(self):
        """Test that optional fields default to None."""
        result = GossMatcherResult()
        assert result.message == ""
        assert result.expected is None
        assert result.actual is None
        assert result.extra_elements is None
        assert result.found_elements is None
        assert result.missing_elements is None


class TestGossResult:
    def test_parse_goss_result(self, passing_command_result_data):
        """Test parsing a complete Goss result."""
        result = GossResult.model_validate(passing_command_result_data)
        assert result.successful is True
        assert result.skipped is False
        assert result.resource_id == "python --version"
        assert result.resource_type == "command"
        assert result.property == "exit-status"
        assert result.duration == 1500000

    def test_parse_failed_result(self, failed_command_result_data):
        """Test parsing a failed Goss result."""
        result = GossResult.model_validate(failed_command_result_data)
        assert result.successful is False
        assert result.skipped is False
        assert result.matcher_result.expected == 0
        assert result.matcher_result.actual == 127


class TestGossSummary:
    def test_summary_success_count(self):
        """Test that success_count is computed correctly."""
        summary = GossSummary(
            **{
                "test-count": 10,
                "failed-count": 2,
                "skipped-count": 1,
                "summary-line": "Count: 10, Failed: 2, Skipped: 1",
                "total-duration": 5000000,
            }
        )
        assert summary.test_count == 10
        assert summary.failed_count == 2
        assert summary.skipped_count == 1
        assert summary.success_count == 7  # 10 - 2 - 1

    def test_summary_all_passed(self):
        """Test summary when all tests pass."""
        summary = GossSummary(
            **{
                "test-count": 5,
                "failed-count": 0,
                "skipped-count": 0,
                "summary-line": "Count: 5, Failed: 0, Skipped: 0",
                "total-duration": 1000000,
            }
        )
        assert summary.success_count == 5

    def test_summary_all_failed(self):
        """Test summary when all tests fail."""
        summary = GossSummary(
            **{
                "test-count": 3,
                "failed-count": 3,
                "skipped-count": 0,
                "summary-line": "Count: 3, Failed: 3, Skipped: 0",
                "total-duration": 500000,
            }
        )
        assert summary.success_count == 0


class TestGossJsonReport:
    def test_create_report(self, passing_command_result_data):
        """Test creating a GossJsonReport."""
        report = GossJsonReport(
            summary=GossSummary(
                **{
                    "test-count": 1,
                    "failed-count": 0,
                    "skipped-count": 0,
                    "summary-line": "Count: 1",
                    "total-duration": 1500000,
                }
            ),
            results=[GossResult.model_validate(passing_command_result_data)],
        )
        assert report.summary.test_count == 1
        assert len(report.results) == 1

    def test_load_from_file(self, tmp_path):
        """Test loading a GossJsonReport from a file."""
        report_data = {
            "summary": {
                "test-count": 2,
                "failed-count": 0,
                "skipped-count": 0,
                "summary-line": "Count: 2",
                "total-duration": 2000000,
            },
            "results": [
                {
                    "successful": True,
                    "skipped": False,
                    "result": 0,
                    "resource-id": "test1",
                    "resource-type": "command",
                    "property": "exit-status",
                    "summary-line": "test1",
                    "summary-line-compact": "test1",
                    "duration": 1000000,
                    "start-time": "2025-01-01T00:00:00Z",
                    "end-time": "2025-01-01T00:00:00.001Z",
                    "matcher-result": {"message": "ok"},
                },
                {
                    "successful": True,
                    "skipped": False,
                    "result": 0,
                    "resource-id": "test2",
                    "resource-type": "file",
                    "property": "exists",
                    "summary-line": "test2",
                    "summary-line-compact": "test2",
                    "duration": 1000000,
                    "start-time": "2025-01-01T00:00:00.001Z",
                    "end-time": "2025-01-01T00:00:00.002Z",
                    "matcher-result": {"message": "ok"},
                },
            ],
        }
        report_file = tmp_path / "goss_report.json"
        report_file.write_text(json.dumps(report_data))

        report = GossJsonReport.load(report_file)
        assert report.summary.test_count == 2
        assert len(report.results) == 2

    def test_test_failures_property(
        self, passing_command_result_data, failed_command_result_data, skipped_command_result_data
    ):
        """Test that test_failures returns only failed (non-skipped) tests."""
        report = GossJsonReport(
            summary=GossSummary(
                **{
                    "test-count": 3,
                    "failed-count": 1,
                    "skipped-count": 1,
                    "summary-line": "Count: 3",
                    "total-duration": 3000000,
                }
            ),
            results=[
                GossResult.model_validate(passing_command_result_data),
                GossResult.model_validate(failed_command_result_data),
                GossResult.model_validate(skipped_command_result_data),
            ],
        )
        failures = report.test_failures
        assert len(failures) == 1
        assert failures[0].resource_id == "missing-cmd"

    def test_test_skips_property(
        self, passing_command_result_data, failed_command_result_data, skipped_command_result_data
    ):
        """Test that test_skips returns only skipped tests."""
        report = GossJsonReport(
            summary=GossSummary(
                **{
                    "test-count": 3,
                    "failed-count": 1,
                    "skipped-count": 1,
                    "summary-line": "Count: 3",
                    "total-duration": 3000000,
                }
            ),
            results=[
                GossResult.model_validate(passing_command_result_data),
                GossResult.model_validate(failed_command_result_data),
                GossResult.model_validate(skipped_command_result_data),
            ],
        )
        skips = report.test_skips
        assert len(skips) == 1
        assert skips[0].resource_id == "optional-feature"

    def test_no_failures(self, passing_command_result_data):
        """Test test_failures when there are no failures."""
        report = GossJsonReport(
            summary=GossSummary(
                **{
                    "test-count": 1,
                    "failed-count": 0,
                    "skipped-count": 0,
                    "summary-line": "Count: 1",
                    "total-duration": 1000000,
                }
            ),
            results=[GossResult.model_validate(passing_command_result_data)],
        )
        assert report.test_failures == []

    def test_no_skips(self, passing_command_result_data):
        """Test test_skips when there are no skipped tests."""
        report = GossJsonReport(
            summary=GossSummary(
                **{
                    "test-count": 1,
                    "failed-count": 0,
                    "skipped-count": 0,
                    "summary-line": "Count: 1",
                    "total-duration": 1000000,
                }
            ),
            results=[GossResult.model_validate(passing_command_result_data)],
        )
        assert report.test_skips == []

    @pytest.mark.parametrize(
        "results_value,property_name",
        [
            pytest.param(None, "test_failures", id="failures-none-results"),
            pytest.param(None, "test_skips", id="skips-none-results"),
            pytest.param([], "test_failures", id="failures-empty-results"),
            pytest.param([], "test_skips", id="skips-empty-results"),
        ],
    )
    def test_empty_results_returns_empty_list(self, results_value, property_name):
        """Test that test_failures and test_skips return empty list for None or empty results."""
        report = GossJsonReport(
            summary=GossSummary(
                **{
                    "test-count": 0,
                    "failed-count": 0,
                    "skipped-count": 0,
                    "summary-line": "Count: 0",
                    "total-duration": 0,
                }
            ),
            results=results_value,
        )
        assert getattr(report, property_name) == []


class TestGossJsonReportCollection:
    @pytest.fixture
    def mock_image_target(self):
        """Create a mock ImageTarget."""
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
    def report_with_failures(
        self, passing_command_result_data, failed_command_result_data, skipped_command_result_data
    ):
        """Create a GossJsonReport with mixed results: 1 pass, 1 fail, 1 skip."""
        return GossJsonReport(
            summary=GossSummary(
                **{
                    "test-count": 3,
                    "failed-count": 1,
                    "skipped-count": 1,
                    "summary-line": "Count: 3",
                    "total-duration": 5000000000,  # 5 seconds
                }
            ),
            results=[
                GossResult.model_validate(passing_command_result_data),
                GossResult.model_validate(failed_command_result_data),
                GossResult.model_validate(skipped_command_result_data),
            ],
        )

    def test_add_report(self, mock_image_target, report_with_failures):
        """Test adding a report to the collection."""
        collection = GossJsonReportCollection()
        collection.add_report(mock_image_target, report_with_failures)

        assert "test-image" in collection
        assert mock_image_target.uid in collection["test-image"]
        target, report = collection["test-image"][mock_image_target.uid]
        assert target is mock_image_target
        assert report is report_with_failures

    def test_add_multiple_reports(self, report_with_failures):
        """Test adding multiple reports to the collection."""
        collection = GossJsonReportCollection()

        target1 = MagicMock(spec=ImageTarget)
        target1.image_name = "image-a"
        target1.uid = "image-a-1.0.0"

        target2 = MagicMock(spec=ImageTarget)
        target2.image_name = "image-a"
        target2.uid = "image-a-2.0.0"

        target3 = MagicMock(spec=ImageTarget)
        target3.image_name = "image-b"
        target3.uid = "image-b-1.0.0"

        collection.add_report(target1, report_with_failures)
        collection.add_report(target2, report_with_failures)
        collection.add_report(target3, report_with_failures)

        assert len(collection) == 2  # Two image names
        assert len(collection["image-a"]) == 2
        assert len(collection["image-b"]) == 1

    def test_test_failures_property(self, failed_command_result_data):
        """Test the test_failures property aggregates failures correctly."""
        collection = GossJsonReportCollection()

        target = MagicMock(spec=ImageTarget)
        target.image_name = "test-image"
        target.uid = "test-uid"

        report = GossJsonReport(
            summary=GossSummary(
                **{
                    "test-count": 2,
                    "failed-count": 1,
                    "skipped-count": 0,
                    "summary-line": "Count: 2",
                    "total-duration": 1000000,
                }
            ),
            results=[GossResult.model_validate(failed_command_result_data)],
        )

        collection.add_report(target, report)
        failures = collection.test_failures

        assert "test-uid" in failures
        assert len(failures["test-uid"]) == 1

    def test_test_failures_no_failures(self, passing_command_result_data):
        """Test test_failures when there are no failures."""
        collection = GossJsonReportCollection()

        target = MagicMock(spec=ImageTarget)
        target.image_name = "test-image"
        target.uid = "test-uid"

        report = GossJsonReport(
            summary=GossSummary(
                **{
                    "test-count": 1,
                    "failed-count": 0,
                    "skipped-count": 0,
                    "summary-line": "Count: 1",
                    "total-duration": 1000000,
                }
            ),
            results=[GossResult.model_validate(passing_command_result_data)],
        )

        collection.add_report(target, report)
        assert collection.test_failures == {}

    def test_aggregate(self, mock_image_target, report_with_failures):
        """Test the aggregate method."""
        collection = GossJsonReportCollection()
        collection.add_report(mock_image_target, report_with_failures)

        aggregated = collection.aggregate()

        assert "total" in aggregated
        assert aggregated["total"]["success"] == 1  # 3 - 1 - 1
        assert aggregated["total"]["failed"] == 1
        assert aggregated["total"]["skipped"] == 1
        assert aggregated["total"]["total_tests"] == 3
        assert aggregated["total"]["duration"] == 5000000000

        assert "test-image" in aggregated
        assert "1.0.0" in aggregated["test-image"]
        assert "ubuntu2204" in aggregated["test-image"]["1.0.0"]
        assert "Standard" in aggregated["test-image"]["1.0.0"]["ubuntu2204"]

    def test_aggregate_multiple_targets(self):
        """Test aggregation with multiple targets."""
        collection = GossJsonReportCollection()

        for version, os_name, variant in [
            ("1.0.0", "ubuntu2204", "Standard"),
            ("1.0.0", "ubuntu2204", "Minimal"),
            ("2.0.0", "ubuntu2404", "Standard"),
        ]:
            target = MagicMock(spec=ImageTarget)
            target.image_name = "test-image"
            target.uid = f"test-image-{version}-{os_name}-{variant}"
            target.image_version = MagicMock()
            target.image_version.name = version
            target.image_variant = MagicMock()
            target.image_variant.name = variant
            target.image_os = MagicMock()
            target.image_os.name = os_name

            report = GossJsonReport(
                summary=GossSummary(
                    **{
                        "test-count": 10,
                        "failed-count": 0,
                        "skipped-count": 0,
                        "summary-line": "Count: 10",
                        "total-duration": 1000000000,
                    }
                ),
                results=[],
            )
            collection.add_report(target, report)

        aggregated = collection.aggregate()

        assert aggregated["total"]["total_tests"] == 30
        assert aggregated["total"]["success"] == 30
        assert aggregated["total"]["duration"] == 3000000000

    def test_aggregate_with_none_variant(self, report_with_failures):
        """Test aggregation when variant is None."""
        collection = GossJsonReportCollection()

        target = MagicMock(spec=ImageTarget)
        target.image_name = "test-image"
        target.uid = "test-uid"
        target.image_version = MagicMock()
        target.image_version.name = "1.0.0"
        target.image_variant = None
        target.image_os = MagicMock()
        target.image_os.name = "ubuntu2204"

        collection.add_report(target, report_with_failures)
        aggregated = collection.aggregate()

        # Should have empty string for variant
        assert "" in aggregated["test-image"]["1.0.0"]["ubuntu2204"]

    def test_aggregate_with_none_os(self, report_with_failures):
        """Test aggregation when OS is None."""
        collection = GossJsonReportCollection()

        target = MagicMock(spec=ImageTarget)
        target.image_name = "test-image"
        target.uid = "test-uid"
        target.image_version = MagicMock()
        target.image_version.name = "1.0.0"
        target.image_variant = MagicMock()
        target.image_variant.name = "Standard"
        target.image_os = None

        collection.add_report(target, report_with_failures)
        aggregated = collection.aggregate()

        # Should have empty string for OS
        assert "" in aggregated["test-image"]["1.0.0"]

    def test_table_generation(self, mock_image_target, report_with_failures):
        """Test that table() generates a Rich table."""
        collection = GossJsonReportCollection()
        collection.add_report(mock_image_target, report_with_failures)

        table = collection.table()

        assert table.title == "Goss Test Results"
        assert len(table.columns) == 9
        # Column headers
        column_names = [col.header for col in table.columns]
        assert "Image Name" in column_names
        assert "Version" in column_names
        assert "OS" in column_names
        assert "Variant" in column_names
        assert "Success" in column_names
        assert "Failed" in column_names
        assert "Skipped" in column_names

    def test_table_with_multiple_rows(self):
        """Test table generation with multiple image targets."""
        collection = GossJsonReportCollection()

        for version in ["1.0.0", "2.0.0"]:
            target = MagicMock(spec=ImageTarget)
            target.image_name = "test-image"
            target.uid = f"test-image-{version}"
            target.image_version = MagicMock()
            target.image_version.name = version
            target.image_variant = MagicMock()
            target.image_variant.name = "Standard"
            target.image_os = MagicMock()
            target.image_os.name = "ubuntu2204"

            report = GossJsonReport(
                summary=GossSummary(
                    **{
                        "test-count": 5,
                        "failed-count": 0 if version == "1.0.0" else 2,
                        "skipped-count": 0,
                        "summary-line": "Count: 5",
                        "total-duration": 1000000000,
                    }
                ),
                results=[],
            )
            collection.add_report(target, report)

        table = collection.table()
        # Should have data rows plus total row
        assert table.row_count >= 2

    def test_empty_collection_aggregate(self):
        """Test aggregate on an empty collection."""
        collection = GossJsonReportCollection()
        aggregated = collection.aggregate()

        assert aggregated["total"]["success"] == 0
        assert aggregated["total"]["failed"] == 0
        assert aggregated["total"]["skipped"] == 0
        assert aggregated["total"]["total_tests"] == 0

    def test_empty_collection_table(self):
        """Test table generation on an empty collection."""
        collection = GossJsonReportCollection()
        table = collection.table()

        # Should still create a valid table with headers
        assert table.title == "Goss Test Results"
