from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import rich
from pydantic import BaseModel, Field, computed_field
from rich.table import Table
from rich.text import Text

from posit_bakery.error import BakeryToolRuntimeErrorGroup
from posit_bakery.models.image.variant import ImageVariant
from posit_bakery.models.project.bake import target_uid


class GossMatcherResult(BaseModel):
    """Models the matcher result of a Goss test case."""

    # Message should be set in all test results, even in skipped tests
    message: Annotated[str, Field(description="Matcher result summary string", default="")]

    # Expected and actual values are set in successful and failed tests, but not skipped tests
    expected: Annotated[
        list | dict | str | int | bool | None, Field(description="Expected value from goss.yaml", default=None)
    ]
    actual: Annotated[
        list | dict | str | int | bool | None, Field(description="Actual value from test result", default=None)
    ]

    # These fields are rarely set, mostly used for more complex matchers and transformations that we don't current use
    # in any of our image Goss tests. The types for these fields are highly variable and can be any JSON supported type
    # (string, number, boolean, array, object) depending on what's being tested. I used "Any" for now since I don't
    # expect type validation to be especially important here.
    extra_elements: Annotated[
        list[Any] | Any | None,
        Field(
            alias="extra-elements",
            description="Lists extra elements that appeared when using 'consist-of' matcher",
            default=None,
        ),
    ]
    found_elements: Annotated[
        list[Any] | Any | None,
        Field(
            alias="found-elements",
            description="Lists all found elements when using 'consist-of' or 'contain-element(s)' matchers",
            default=None,
        ),
    ]
    missing_elements: Annotated[
        list[Any] | Any | None,
        Field(
            alias="missing-elements",
            description=(
                "Lists all missing elements when using 'consist-of', 'have_patterns', or 'contain-element(s)' matchers"
            ),
            default=None,
        ),
    ]
    transform_chain: Annotated[
        Any | None,
        Field(
            alias="transform-chain",
            description=(
                "Lists any transformations applied to system state (actual) type in attempt to match expected type"
            ),
            default=None,
        ),
    ]
    untransformed_value: Annotated[
        Any | None,
        Field(
            alias="untransformed-value",
            description="Shows raw system state value if transformations were applied",
            default=None,
        ),
    ]


class GossResult(BaseModel):
    """Models the result of a single Goss test case."""

    successful: Annotated[bool, Field(description="Whether the test was successful")]
    skipped: Annotated[bool, Field(description="Whether the test was skipped")]
    err: Annotated[str | None, Field(description="Error message if Goss failed to execute the test", default=None)]
    result: Annotated[int, Field(description="Exit code from Goss test subprocess call")]

    resource_id: Annotated[str, Field(alias="resource-id", description="Test key in goss.yaml")]
    resource_type: Annotated[str, Field(alias="resource-type", description="Test type/section in goss.yaml")]
    property: Annotated[str, Field(alias="property", description="Element of test being checked")]
    title: Annotated[str, Field(description="Test title from goss.yaml (if present)", default="")]
    summary_line: Annotated[str, Field(alias="summary-line", description="Test summary string")]
    summary_line_compact: Annotated[
        str, Field(alias="summary-line-compact", description="One-liner test summary string")
    ]

    duration: Annotated[int, Field(description="Test duration in nanoseconds")]
    start_time: Annotated[
        datetime, Field(alias="start-time", description="Test start time in UTC, parsed from ISO 8601")
    ]
    end_time: Annotated[datetime, Field(alias="end-time", description="Test end time in UTC, parsed from ISO 8601")]

    matcher_result: Annotated[
        GossMatcherResult, Field(alias="matcher-result", description="Matcher result object, detailed test result data")
    ]
    meta: Annotated[dict[str, Any] | None, Field(description="Arbitrary metadata added by Goss", default=None)]


class GossSummary(BaseModel):
    """Models the summary section of a Goss JSON report."""

    test_count: Annotated[int, Field(alias="test-count", description="Total number of tests")]
    failed_count: Annotated[int, Field(alias="failed-count", description="Number of failed tests")]
    skipped_count: Annotated[int, Field(alias="skipped-count", description="Number of skipped tests")]
    summary_line: Annotated[str, Field(alias="summary-line", description="Summary string of test results")]
    total_duration: Annotated[int, Field(alias="total-duration", description="Total test duration in nanoseconds")]

    @computed_field(alias="success-count")
    @property
    def success_count(self) -> int:
        return self.test_count - self.failed_count - self.skipped_count


class GossJsonReport(BaseModel):
    """Models Goss JSON reports produced by goss tests with `--format json`."""

    filepath: Annotated[Path | None, Field(default=None, exclude=True)]
    summary: GossSummary
    results: list[GossResult] | None = None

    @classmethod
    def load(cls, filepath: Path) -> "GossJsonReport":
        """Load a Goss JSON report from a file."""
        with filepath.open("r") as file:
            data = cls.model_validate_json(file.read())
        return data

    @property
    def test_failures(self) -> list[GossResult]:
        tests = []
        for result in self.results:
            if not result.successful and not result.skipped:
                tests.append(result)
        return tests

    @property
    def test_skips(self) -> list[GossResult]:
        tests = []
        for result in self.results:
            if result.skipped:
                tests.append(result)
        return tests


class GossJsonReportCollection(dict):
    def add_report(self, variant: ImageVariant, report: GossJsonReport):
        """Adds a GossJsonReport to the collection."""
        if variant.meta.name not in self:
            self[variant.meta.name] = {}
        self[variant.meta.name][target_uid(variant.meta.name, variant.meta.version, variant)] = (variant, report)

    @property
    def test_failures(self) -> dict[str, list[GossResult]]:
        failures = {}
        for image_name, targets in self.items():
            for uid, (_, report) in targets.items():
                if not report.test_failures:
                    continue
                if uid not in failures:
                    failures[uid] = []
                for failure in report.test_failures:
                    failures[uid].append(failure)
        return failures

    def aggregate(self) -> dict[str, dict]:
        results = {"total": {"success": 0, "failed": 0, "skipped": 0, "total_tests": 0, "duration": 0}}
        for image_name, targets in self.items():
            for uid, (variant, report) in targets.items():
                if variant.meta.name not in results:
                    results[variant.meta.name] = {}
                if variant.meta.version not in results[variant.meta.name]:
                    results[variant.meta.name][variant.meta.version] = {}
                if variant.target not in results[variant.meta.name][variant.meta.version]:
                    results[variant.meta.name][variant.meta.version][variant.target] = {}
                results[variant.meta.name][variant.meta.version][variant.target] = {
                    "success": report.summary.success_count,
                    "failed": report.summary.failed_count,
                    "skipped": report.summary.skipped_count,
                    "total_tests": report.summary.test_count,
                    "duration": report.summary.total_duration,
                }
                results["total"]["success"] += report.summary.success_count
                results["total"]["failed"] += report.summary.failed_count
                results["total"]["skipped"] += report.summary.skipped_count
                results["total"]["total_tests"] += report.summary.test_count
                results["total"]["duration"] += report.summary.total_duration
        results["total"]["duration"] = results["total"]["duration"]
        return results

    def table(self) -> Table:
        """Generates a rich table of the test results."""
        aggregated_results = self.aggregate()
        total_row = aggregated_results.pop("total")

        table = Table(title="Goss Test Results")
        table.add_column("Image Name", justify="left")
        table.add_column("Version", justify="left")
        table.add_column("Target", justify="left")
        table.add_column("Success", justify="right", header_style="green3")
        table.add_column("Failed", justify="right", header_style="bright_red")
        table.add_column("Skipped", justify="right", header_style="yellow")
        table.add_column("Total Tests", justify="right")
        table.add_column("Duration", justify="right")

        for image_name, versions in aggregated_results.items():
            p_image_name = image_name
            for version, target_types in versions.items():
                p_version = version
                for target_type, result in target_types.items():
                    success_style = "green3 bold" if result["failed"] == 0 else ""
                    failed_style = "bright_red bold" if result["failed"] > 0 else "bright_black italic"
                    skipped_style = "yellow bold" if result["skipped"] > 0 else "bright_black italic"
                    table.add_row(
                        p_image_name,
                        p_version,
                        target_type,
                        Text(str(result["success"]), style=success_style),
                        Text(str(result["failed"]), style=failed_style),
                        Text(str(result["skipped"]), style=skipped_style),
                        str(result["total_tests"]),
                        f"{result['duration'] / 1_000_000_000:.2f}s",
                    )
                    p_image_name = ""
                    p_version = ""

        table.add_section()
        table.add_row(
            "Total",
            "",
            "",
            str(total_row["success"]),
            str(total_row["failed"]),
            str(total_row["skipped"]),
            str(total_row["total_tests"]),
            f"{total_row['duration'] / 1_000_000_000:.2f}s",
        )

        return table
