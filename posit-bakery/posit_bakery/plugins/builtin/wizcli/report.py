import json
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
        with filepath.open("r") as f:
            data = json.load(f)

        with filepath.open("w") as f:
            json.dump(data, f, indent=2)

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


class WizScanReportCollection(dict):
    """Collection of WizScanReports keyed by image_name -> {uid: (target, report)}."""

    def add_report(self, image_target: ImageTarget, report: WizScanReport):
        self.setdefault(image_target.image_name, dict())[image_target.uid] = (image_target, report)

    def aggregate(self) -> dict:
        totals = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        results = {"total": totals}

        for image_name, targets in self.items():
            for uid, (target, report) in targets.items():
                variant_name = target.image_variant.name if target.image_variant else ""
                os_name = target.image_os.name if target.image_os else ""
                version_name = target.image_version.name

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
                        critical_style = "bright_red bold" if row["critical"] > 0 else "bright_black italic"
                        high_style = "red bold" if row["high"] > 0 else "bright_black italic"
                        medium_style = "yellow bold" if row["medium"] > 0 else "bright_black italic"
                        low_style = "bright_blue bold" if row["low"] > 0 else "bright_black italic"
                        info_style = "bright_black"

                        table.add_row(
                            p_image_name,
                            p_version,
                            variant_name,
                            p_os,
                            row["verdict"],
                            Text(str(row["critical"]), style=critical_style),
                            Text(str(row["high"]), style=high_style),
                            Text(str(row["medium"]), style=medium_style),
                            Text(str(row["low"]), style=low_style),
                            Text(str(row["info"]), style=info_style),
                            row.get("report_url") or "",
                        )
                        p_image_name = ""
                        p_version = ""
                        p_os = ""

        table.add_section()
        table.add_row(
            "Total", "", "", "", "",
            str(total_row["critical"]),
            str(total_row["high"]),
            str(total_row["medium"]),
            str(total_row["low"]),
            str(total_row["info"]),
            "",
        )

        return table
