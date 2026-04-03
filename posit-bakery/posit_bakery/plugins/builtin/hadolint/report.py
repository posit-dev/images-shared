import json
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field
from rich.table import Table
from rich.text import Text

from posit_bakery.image.image_target import ImageTarget


class HadolintResult(BaseModel):
    """Models a single lint issue from hadolint JSON output."""

    code: Annotated[str, Field(description="Rule code, e.g. DL3008")]
    column: Annotated[int, Field(description="Column number")]
    file: Annotated[str, Field(description="File path as hadolint reported it")]
    level: Annotated[str, Field(description="Severity level: error, warning, info, style")]
    line: Annotated[int, Field(description="Line number")]
    message: Annotated[str, Field(description="Human-readable description")]


class HadolintReport(BaseModel):
    """Holds all hadolint results for a single image target."""

    filepath: Annotated[Path | None, Field(default=None, exclude=True, description="Path to the results JSON file.")]
    containerfile: Annotated[Path, Field(description="Relative path to the Containerfile.")]
    exit_code: Annotated[int, Field(default=0, exclude=True, description="Hadolint process exit code.")]
    results: Annotated[list[HadolintResult], Field(default_factory=list, description="List of lint issues.")]

    @classmethod
    def load(cls, filepath: Path, containerfile: Path) -> "HadolintReport":
        """Load a HadolintReport from a JSON results file."""
        with filepath.open("r") as f:
            data = json.load(f)
        results = [HadolintResult.model_validate(item) for item in data]
        return cls(filepath=filepath, containerfile=containerfile, results=results)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.level == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.results if r.level == "warning")

    @property
    def info_count(self) -> int:
        return sum(1 for r in self.results if r.level == "info")

    @property
    def style_count(self) -> int:
        return sum(1 for r in self.results if r.level == "style")

    @property
    def total_count(self) -> int:
        return len(self.results)

    def by_level(self, level: str) -> list[HadolintResult]:
        """Return results filtered to a specific severity level."""
        return [r for r in self.results if r.level == level]


class HadolintReportCollection(dict):
    """Collection of HadolintReports keyed by image name and UID."""

    def add_report(self, image_target: ImageTarget, report: HadolintReport):
        """Add a HadolintReport to the collection."""
        self.setdefault(image_target.image_name, dict())[image_target.uid] = (image_target, report)

    @property
    def has_issues(self) -> bool:
        """Return True if any report has lint issues."""
        for image_name, targets in self.items():
            for uid, (_, report) in targets.items():
                if report.total_count > 0:
                    return True
        return False

    def table(self) -> Table:
        """Generate a Rich table summarizing lint results."""
        table = Table(title="Hadolint Results")
        table.add_column("Image Name", justify="left")
        table.add_column("Version", justify="left")
        table.add_column("OS", justify="left")
        table.add_column("Variant", justify="left")
        table.add_column("Errors", justify="right", header_style="bright_red")
        table.add_column("Warnings", justify="right", header_style="yellow")
        table.add_column("Info", justify="right", header_style="bright_blue")
        table.add_column("Style", justify="right", header_style="bright_black")
        table.add_column("Total", justify="right")

        total_errors = 0
        total_warnings = 0
        total_info = 0
        total_style = 0

        for image_name, targets in self.items():
            p_image_name = image_name
            for uid, (target, report) in targets.items():
                variant_name = target.image_variant.name if target.image_variant else ""
                os_name = target.image_os.name if target.image_os else ""
                version_name = target.image_version.name

                error_style = "bright_red bold" if report.error_count > 0 else "bright_black italic"
                warning_style = "yellow bold" if report.warning_count > 0 else "bright_black italic"
                info_style = "bright_blue bold" if report.info_count > 0 else "bright_black italic"
                style_style = "bright_black italic"

                table.add_row(
                    p_image_name,
                    version_name,
                    os_name,
                    variant_name,
                    Text(str(report.error_count), style=error_style),
                    Text(str(report.warning_count), style=warning_style),
                    Text(str(report.info_count), style=info_style),
                    Text(str(report.style_count), style=style_style),
                    str(report.total_count),
                )
                p_image_name = ""

                total_errors += report.error_count
                total_warnings += report.warning_count
                total_info += report.info_count
                total_style += report.style_count

        table.add_section()
        table.add_row(
            "Total", "", "", "",
            str(total_errors),
            str(total_warnings),
            str(total_info),
            str(total_style),
            str(total_errors + total_warnings + total_info + total_style),
        )

        return table
