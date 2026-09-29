import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field
from rich.table import Table
from rich.text import Text

from posit_bakery.image.image_target import ImageTarget

# CVSS v3 severity thresholds (NVD convention), used to bucket a SARIF rule's
# `security-severity` score when trivy provides one (vulnerability findings).
_CVSS_CRITICAL_THRESHOLD = 9.0
_CVSS_HIGH_THRESHOLD = 7.0
_CVSS_MEDIUM_THRESHOLD = 4.0
_CVSS_LOW_THRESHOLD = 0.1

# SARIF `level` -> severity bucket, used when a rule carries no `security-severity`
# score (trivy sets this for misconfigurations/secrets, which have no CVSS score).
_SARIF_LEVEL_SEVERITY = {
    "error": "high",
    "warning": "medium",
    "note": "low",
    "none": "info",
}


def _severity_from_security_severity(score: float) -> str:
    if score >= _CVSS_CRITICAL_THRESHOLD:
        return "critical"
    if score >= _CVSS_HIGH_THRESHOLD:
        return "high"
    if score >= _CVSS_MEDIUM_THRESHOLD:
        return "medium"
    if score >= _CVSS_LOW_THRESHOLD:
        return "low"
    return "info"


class TrivyScanReport(BaseModel):
    """Lightweight model for trivy SARIF scan output.

    Captures aggregated vulnerability severity counts by bucketing SARIF
    ``runs[].results[]`` against their ``runs[].tool.driver.rules[]`` metadata,
    without modeling the full SARIF schema.
    """

    filepath: Annotated[Path | None, Field(default=None, exclude=True)]
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0

    @property
    def total_count(self) -> int:
        return self.critical_count + self.high_count + self.medium_count + self.low_count + self.info_count

    @classmethod
    def load(cls, filepath: Path) -> "TrivyScanReport":
        """Load a TrivyScanReport from a trivy SARIF output file.

        Re-writes the file with indentation for human readability, since trivy
        outputs minified SARIF by default.
        """
        raw = filepath.read_text()
        data = json.loads(raw)

        if "runs" not in data:
            # A syntactically-valid JSON payload that isn't SARIF (e.g. `{}`) must
            # not be silently treated as an empty, passing report -- a future
            # trivy release changing its output shape should surface as a scan
            # failure here, not as "0 vulnerabilities found".
            raise ValueError("trivy results file is not a valid SARIF report (missing 'runs')")

        # Re-write with indentation for human readability if the file is minified.
        # Include a trailing newline so the output matches POSIX/end-of-file-fixer
        # conventions; otherwise an already-formatted file would be rewritten on
        # every load (stripping the newline) and ping-pong against pre-commit.
        formatted = json.dumps(data, indent=2) + "\n"
        if formatted != raw:
            filepath.write_text(formatted)

        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}

        for run in data.get("runs", []) or []:
            rules = run.get("tool", {}).get("driver", {}).get("rules", []) or []
            # Index rules by id for O(1) lookup per result; a SARIF run can carry
            # hundreds of results against the same handful of rules.
            rules_by_id = {rule["id"]: rule for rule in rules if "id" in rule}

            for result in run.get("results", []) or []:
                rule = rules_by_id.get(result.get("ruleId"))

                if rule is None:
                    # An unresolvable ruleId leaves no metadata to bucket against;
                    # treat it as informational rather than dropping it, so every
                    # result is still accounted for in total_count.
                    counts["info"] += 1
                    continue

                security_severity = rule.get("properties", {}).get("security-severity")
                if security_severity is not None:
                    severity = _severity_from_security_severity(float(security_severity))
                else:
                    level = rule.get("defaultConfiguration", {}).get("level", "none")
                    severity = _SARIF_LEVEL_SEVERITY.get(level, "info")

                counts[severity] += 1

        return cls(
            filepath=filepath,
            critical_count=counts["critical"],
            high_count=counts["high"],
            medium_count=counts["medium"],
            low_count=counts["low"],
            info_count=counts["info"],
        )


@dataclass(frozen=True)
class TrivyScanFailure:
    """Recorded in place of a TrivyScanReport when a scan produced nothing to parse.

    A dedicated type -- rather than a bare ``str`` verdict living in the same slot as
    a ``TrivyScanReport`` -- keeps "did this scan fail" a matter of type, not of
    ``isinstance(report, str)`` happening to be true. Mirrors ``WizScanFailure``.
    """

    verdict: str


class TrivyReportCollection(dict):
    """Collection of TrivyScanReports keyed by image_name -> {uid: (target, report)}."""

    def add_report(self, image_target: ImageTarget, report: TrivyScanReport):
        self.setdefault(image_target.image_name, dict())[image_target.uid] = (image_target, report)

    def add_failure(self, image_target: ImageTarget, verdict: str = "SCAN FAILED"):
        """Record a target whose scan produced no parseable report.

        Failed targets are kept in the collection so they appear in the results
        table. Omitting them would render a table that looks complete while
        silently covering only the targets that happened to scan successfully.
        """
        self.setdefault(image_target.image_name, dict())[image_target.uid] = (
            image_target,
            TrivyScanFailure(verdict=verdict),
        )

    def aggregate(self) -> dict:
        totals = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        results = {"total": totals}

        for image_name, targets in self.items():
            for uid, (target, report) in targets.items():
                variant_name = target.image_variant.name if target.image_variant else ""
                os_name = target.image_os.name if target.image_os else ""
                version_name = target.image_version.name

                if isinstance(report, TrivyScanFailure):
                    # Failed scan: severity counts are unknown, not zero, so they are
                    # rendered as None and excluded from the totals rather than
                    # understating them.
                    row = {
                        "critical": None,
                        "high": None,
                        "medium": None,
                        "low": None,
                        "info": None,
                        "status": report.verdict,
                    }
                else:
                    row = {
                        "critical": report.critical_count,
                        "high": report.high_count,
                        "medium": report.medium_count,
                        "low": report.low_count,
                        "info": report.info_count,
                        "status": "OK",
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

        table = Table(title="Trivy Scan Results")
        table.add_column("Image Name", justify="left")
        table.add_column("Version", justify="left")
        table.add_column("Variant", justify="left")
        table.add_column("OS", justify="left")
        table.add_column("Status", justify="left")
        table.add_column("Critical", justify="right", header_style="bright_red")
        table.add_column("High", justify="right", header_style="red")
        table.add_column("Medium", justify="right", header_style="yellow")
        table.add_column("Low", justify="right", header_style="bright_blue")
        table.add_column("Info", justify="right", header_style="bright_black")

        for image_name, versions in aggregated.items():
            p_image_name = image_name
            for version, oses in versions.items():
                p_version = version
                for os_name, variants in oses.items():
                    p_os = os_name
                    for variant_name, row in variants.items():
                        failed = row["critical"] is None

                        def count(key: str, style: str, row: dict = row) -> Text:
                            # Unknown counts render as "-" so a failed scan is never
                            # mistaken for a clean one. `row` is bound as a default
                            # argument, not captured by reference, so each call reads
                            # the row from its own loop iteration rather than whatever
                            # `row` is bound to when the closure is finally invoked (B023).
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
                            Text(row["status"], style="red bold") if failed else row["status"],
                            count("critical", critical_style),
                            count("high", high_style),
                            count("medium", medium_style),
                            count("low", low_style),
                            count("info", info_style),
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
        )

        return table
