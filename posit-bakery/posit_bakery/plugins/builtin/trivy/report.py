import json
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field
from rich.table import Table
from rich.text import Text

from posit_bakery.image.image_target import ImageTarget

_SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN")


class TrivyReport(BaseModel):
    """Lightweight model for Trivy SARIF scan output.

    Captures per-severity finding counts by cross-referencing each SARIF result's
    `ruleId` against its rule's `properties.tags` severity tag, without modeling
    the full SARIF schema.
    """

    filepath: Annotated[Path | None, Field(default=None, exclude=True)]
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    unknown_count: int = 0

    @property
    def total_count(self) -> int:
        return self.critical_count + self.high_count + self.medium_count + self.low_count + self.unknown_count

    def breaches(self, severities: list[str]) -> bool:
        """Return True if any of the given severities has at least one finding."""
        counts = {
            "CRITICAL": self.critical_count,
            "HIGH": self.high_count,
            "MEDIUM": self.medium_count,
            "LOW": self.low_count,
            "UNKNOWN": self.unknown_count,
        }
        return any(counts.get(sev.strip().upper(), 0) > 0 for sev in severities)

    @classmethod
    def load(cls, filepath: Path) -> "TrivyReport":
        """Load a TrivyReport from a Trivy SARIF output file.

        Re-writes the file with indentation for human readability, since Trivy
        outputs minified JSON by default.
        """
        raw = filepath.read_text()
        data = json.loads(raw)

        formatted = json.dumps(data, indent=2) + "\n"
        if formatted != raw:
            filepath.write_text(formatted)

        counts = {sev: 0 for sev in _SEVERITIES}

        for run in data.get("runs", []) or []:
            rules = run.get("tool", {}).get("driver", {}).get("rules", []) or []
            severity_by_rule_id = {}
            for rule in rules:
                tags = rule.get("properties", {}).get("tags", []) or []
                severity = next((t for t in tags if t in _SEVERITIES), "UNKNOWN")
                severity_by_rule_id[rule["id"]] = severity

            for result in run.get("results", []) or []:
                severity = severity_by_rule_id.get(result.get("ruleId"), "UNKNOWN")
                counts[severity] += 1

        return cls(
            filepath=filepath,
            critical_count=counts["CRITICAL"],
            high_count=counts["HIGH"],
            medium_count=counts["MEDIUM"],
            low_count=counts["LOW"],
            unknown_count=counts["UNKNOWN"],
        )


class TrivyReportCollection(dict):
    """Collection of TrivyReports keyed by image_name -> {uid: (target, report)}."""

    def add_report(self, image_target: ImageTarget, report: TrivyReport):
        self.setdefault(image_target.image_name, dict())[image_target.uid] = (image_target, report)

    def aggregate(self) -> dict:
        totals = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0}
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
                    "unknown": report.unknown_count,
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

        table = Table(title="Trivy Scan Results")
        table.add_column("Image Name", justify="left")
        table.add_column("Version", justify="left")
        table.add_column("Variant", justify="left")
        table.add_column("OS", justify="left")
        table.add_column("Critical", justify="right", header_style="bright_red")
        table.add_column("High", justify="right", header_style="red")
        table.add_column("Medium", justify="right", header_style="yellow")
        table.add_column("Low", justify="right", header_style="bright_blue")
        table.add_column("Unknown", justify="right", header_style="bright_black")

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
                        unknown_style = "bright_black"

                        table.add_row(
                            p_image_name,
                            p_version,
                            variant_name,
                            p_os,
                            Text(str(row["critical"]), style=critical_style),
                            Text(str(row["high"]), style=high_style),
                            Text(str(row["medium"]), style=medium_style),
                            Text(str(row["low"]), style=low_style),
                            Text(str(row["unknown"]), style=unknown_style),
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
            str(total_row["critical"]),
            str(total_row["high"]),
            str(total_row["medium"]),
            str(total_row["low"]),
            str(total_row["unknown"]),
        )

        return table
