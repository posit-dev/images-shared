import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field
from rich.table import Table
from rich.text import Text

from posit_bakery.image.image_target import ImageTarget


class WizScanReport(BaseModel):
    """Lightweight model for wizcli scan JSON output.

    Captures scan metadata and aggregated vulnerability severity counts without modeling
    the full wizcli JSON schema.
    """

    filepath: Annotated[Path | None, Field(default=None, exclude=True)]
    scan_id: str
    status_state: str
    status_verdict: str
    report_url: str | None
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0

    @property
    def total_count(self) -> int:
        return self.critical_count + self.high_count + self.medium_count + self.low_count + self.info_count

    @classmethod
    def load(cls, filepath: Path) -> "WizScanReport":
        """Load a WizScanReport from a wizcli JSON output file.

        Re-writes the file with indentation for human readability, since wizcli
        outputs minified JSON by default.
        """
        raw = filepath.read_text()
        data = json.loads(raw)

        # Re-write with indentation for human readability if the file is minified.
        # Include a trailing newline so the output matches POSIX/end-of-file-fixer
        # conventions; otherwise an already-formatted file would be rewritten on
        # every load (stripping the newline) and ping-pong against pre-commit.
        formatted = json.dumps(data, indent=2) + "\n"
        if formatted != raw:
            filepath.write_text(formatted)

        # Aggregate severity counts from vulnerable SBOM artifacts
        critical = high = medium = low = info = 0
        for artifact in data.get("result", {}).get("vulnerableSBOMArtifactsByNameVersion", []) or []:
            severities = artifact.get("vulnerabilityFindings", {}).get("severities", {})
            critical += severities.get("criticalCount", 0)
            high += severities.get("highCount", 0)
            medium += severities.get("mediumCount", 0)
            low += severities.get("lowCount", 0)
            info += severities.get("infoCount", 0)

        # Only treat reportUrl as a real URL if it starts with http
        raw_url = data.get("reportUrl")
        report_url = raw_url if raw_url and raw_url.startswith("http") else None

        return cls(
            filepath=filepath,
            scan_id=data["id"],
            status_state=data["status"]["state"],
            status_verdict=data["status"]["verdict"],
            report_url=report_url,
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            low_count=low,
            info_count=info,
        )


@dataclass(frozen=True)
class WizScanFailure:
    """Recorded in place of a WizScanReport when a scan produced nothing to parse.

    A dedicated type -- rather than a bare ``str`` verdict living in the same slot as a
    ``WizScanReport`` -- keeps "did this scan fail" a matter of type, not of
    ``isinstance(report, str)`` happening to be true.
    """

    verdict: str


class WizScanReportCollection(dict):
    """Collection of WizScanReports keyed by image_name -> {uid: (target, report)}."""

    def add_report(self, image_target: ImageTarget, report: WizScanReport):
        self.setdefault(image_target.image_name, dict())[image_target.uid] = (image_target, report)

    def add_failure(self, image_target: ImageTarget, verdict: str = "SCAN FAILED"):
        """Record a target whose scan produced no parseable report.

        Failed targets are kept in the collection so they appear in the results table.
        Omitting them would render a table that looks complete while silently covering
        only the targets that happened to scan successfully.
        """
        self.setdefault(image_target.image_name, dict())[image_target.uid] = (
            image_target,
            WizScanFailure(verdict=verdict),
        )

    def aggregate(self) -> dict:
        totals = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        results = {"total": totals}

        for image_name, targets in self.items():
            for uid, (target, report) in targets.items():
                variant_name = target.image_variant.name if target.image_variant else ""
                os_name = target.image_os.name if target.image_os else ""
                version_name = target.image_version.name

                if isinstance(report, WizScanFailure):
                    # Failed scan: severity counts are unknown, not zero, so they are rendered
                    # as None and excluded from the totals rather than understating them.
                    row = {
                        "critical": None,
                        "high": None,
                        "medium": None,
                        "low": None,
                        "info": None,
                        "verdict": report.verdict,
                        "report_url": None,
                    }
                else:
                    row = {
                        "critical": report.critical_count,
                        "high": report.high_count,
                        "medium": report.medium_count,
                        "low": report.low_count,
                        "info": report.info_count,
                        "verdict": report.status_verdict,
                        "report_url": report.report_url,
                    }

                results.setdefault(image_name, {})
                results[image_name].setdefault(version_name, {})
                results[image_name][version_name].setdefault(os_name, {})
                results[image_name][version_name][os_name][variant_name] = row

                for key in totals:
                    if row[key] is not None:
                        totals[key] += row[key]

        return results

    def table(self) -> Table:
        aggregated = self.aggregate()
        total_row = aggregated.pop("total")

        table = Table(title="WizCLI Scan Results")
        table.add_column("Image Name", justify="left")
        table.add_column("Version", justify="left")
        table.add_column("Variant", justify="left")
        table.add_column("OS", justify="left")
        table.add_column("Verdict", justify="left")
        table.add_column("Critical", justify="right", header_style="bright_red")
        table.add_column("High", justify="right", header_style="red")
        table.add_column("Medium", justify="right", header_style="yellow")
        table.add_column("Low", justify="right", header_style="bright_blue")
        table.add_column("Info", justify="right", header_style="bright_black")
        table.add_column("Report URL", justify="left")

        for image_name, versions in aggregated.items():
            p_image_name = image_name
            for version, oses in versions.items():
                p_version = version
                for os_name, variants in oses.items():
                    p_os = os_name
                    for variant_name, row in variants.items():
                        failed = row["critical"] is None

                        def count(key: str, style: str, row: dict = row) -> Text:
                            # Unknown counts render as "-" so a failed scan is never mistaken
                            # for a clean one. `row` is bound as a default argument, not
                            # captured by reference, so each call reads the row from its own
                            # loop iteration rather than whatever `row` is bound to when the
                            # closure is finally invoked (B023).
                            if row[key] is None:
                                return Text("-", style="bright_black italic")
                            return Text(str(row[key]), style=style)

                        critical_style = (
                            "bright_red bold" if not failed and row["critical"] > 0 else "bright_black italic"
                        )
                        high_style = "red bold" if not failed and row["high"] > 0 else "bright_black italic"
                        medium_style = "yellow bold" if not failed and row["medium"] > 0 else "bright_black italic"
                        low_style = "bright_blue bold" if not failed and row["low"] > 0 else "bright_black italic"
                        info_style = "bright_black"

                        table.add_row(
                            p_image_name,
                            p_version,
                            variant_name,
                            p_os,
                            Text(row["verdict"], style="red bold") if failed else row["verdict"],
                            count("critical", critical_style),
                            count("high", high_style),
                            count("medium", medium_style),
                            count("low", low_style),
                            count("info", info_style),
                            row.get("report_url") or "",
                        )
                        p_image_name = ""
                        p_version = ""
                        p_os = ""

        table.add_section()
        table.add_row(
            "Total",
            "",
            "",
            "",
            "",
            str(total_row["critical"]),
            str(total_row["high"]),
            str(total_row["medium"]),
            str(total_row["low"]),
            str(total_row["info"]),
            "",
        )

        return table
