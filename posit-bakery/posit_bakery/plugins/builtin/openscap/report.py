"""Parsing, validation and rendering of OpenSCAP scan results."""

import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

from rich.table import Table
from rich.text import Text

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.openscap.content import RULE_PREFIX
from posit_bakery.plugins.builtin.openscap.options import FailOnEnum

XCCDF_NS = "{http://checklists.nist.gov/xccdf/1.2}"

RESULT_TYPES = (
    "pass",
    "fail",
    "error",
    "unknown",
    "notapplicable",
    "notchecked",
    "notselected",
    "informational",
    "fixed",
)
# Results that need a human/agent to look at them.
FINDING_RESULTS = ("fail", "error", "unknown", "notchecked")
SEVERITY_RANK = {"unknown": 0, "low": 1, "medium": 2, "high": 3}
FAIL_ON_RANK = {FailOnEnum.ANY: 0, FailOnEnum.LOW: 1, FailOnEnum.MEDIUM: 2, FailOnEnum.HIGH: 3}
# A file rule present in every Linux CIS profile; it must evaluate against a correctly mounted rootfs.
CANARY_RULE = "file_permissions_etc_passwd"

_FIX_BLOCK_RE = re.compile(r"# BEGIN fix \(\d+ / \d+\) for '([^']+)'\n#+\n(.*?)\n# END fix for '\1'", re.DOTALL)
_FIX_ECHO_RE = re.compile(r"^\(>&2 echo \"Remediating rule .*\"\)\n", re.MULTILINE)


def _text(el: ET.Element | None) -> str:
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def short_rule_id(rule_id: str) -> str:
    return rule_id.removeprefix(RULE_PREFIX)


@dataclass
class Finding:
    id: str
    title: str
    severity: str
    result: str
    cis_refs: list[str] = field(default_factory=list)
    rationale: str = ""
    fix_bash: str | None = None
    ignored: bool = False


@dataclass
class ValidationCheck:
    name: str
    ok: bool
    detail: str


def parse_fix_script(text: str) -> dict[str, str]:
    """Split an `oscap xccdf generate fix --fix-type bash` script into per-rule snippets keyed by short rule ID."""
    return {
        short_rule_id(rule_id): re.sub(r"\n{3,}", "\n\n", _FIX_ECHO_RE.sub("", body)).strip()
        for rule_id, body in _FIX_BLOCK_RE.findall(text)
    }


def validate_scan(
    *,
    product: str | None,
    os_release: dict[str, str],
    counts: dict[str, int],
    results: dict[str, str],
    arf_text: str | None,
) -> list[ValidationCheck]:
    """Check that the scan evaluated the target image rootfs rather than the scanner host or nothing at all."""
    checks = []
    version_id = os_release.get("VERSION_ID", "")

    if arf_text is not None:
        os_name = re.search(r"<(?:[\w.-]+:)?os_name>([^<]*)<", arf_text)
        os_version = re.search(r"<(?:[\w.-]+:)?os_version>([^<]*)<", arf_text)
        seen = f"{os_name.group(1) if os_name else '?'} {os_version.group(1) if os_version else '?'}"
        ok = bool(
            os_name
            and os_version
            and os_name.group(1).strip() == os_release.get("NAME", "").strip()
            and os_version.group(1).startswith(version_id)
        )
        checks.append(ValidationCheck("system_info", ok, f"scanned system reported as '{seen}'"))

        if product:
            definition = f"oval:ssg-installed_OS_is_{product}:def:1"
            states = re.findall(rf'definition_id="{re.escape(definition)}" result="([^"]+)"', arf_text)
            if states:
                ok = "true" in states
                checks.append(ValidationCheck("installed_os", ok, f"{definition} evaluated {sorted(set(states))}"))

    canary = results.get(CANARY_RULE)
    if canary is not None and canary != "notselected":
        checks.append(ValidationCheck("canary_rule", canary in ("pass", "fail"), f"{CANARY_RULE} evaluated '{canary}'"))

    evaluated = counts.get("pass", 0) + counts.get("fail", 0)
    checks.append(ValidationCheck("evaluated_rules", evaluated > 0, f"{evaluated} rules passed or failed"))
    return checks


@dataclass
class OpenSCAPScanReport:
    product: str | None
    profile_id: str
    content: str
    os_release: dict[str, str]
    counts: dict[str, int]
    findings: list[Finding]
    checks: list[ValidationCheck]
    files: dict[str, str] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return all(c.ok for c in self.checks)

    def severity_counts(self) -> dict[str, int]:
        counts = {s: 0 for s in SEVERITY_RANK}
        for f in self.findings:
            if f.result == "fail" and not f.ignored:
                counts[f.severity if f.severity in counts else "unknown"] += 1
        return counts

    def breached(self, fail_on: FailOnEnum) -> bool:
        if fail_on == FailOnEnum.NONE:
            return False
        threshold = FAIL_ON_RANK[fail_on]
        return any(
            f.result == "fail" and not f.ignored and SEVERITY_RANK.get(f.severity, 0) >= threshold
            for f in self.findings
        )

    @classmethod
    def load(
        cls,
        results_file: Path,
        *,
        profile_id: str,
        content: str,
        product: str | None,
        os_release: dict[str, str],
        arf_file: Path | None = None,
        fix_file: Path | None = None,
        skip_rules: list[str] | None = None,
    ) -> "OpenSCAPScanReport":
        root = ET.parse(results_file).getroot()
        rules = {}
        for rule in root.iter(f"{XCCDF_NS}Rule"):
            rules[rule.get("id")] = rule

        test_results = list(root.iter(f"{XCCDF_NS}TestResult"))
        if not test_results:
            raise ValueError(f"No TestResult in {results_file}")
        results: dict[str, tuple[str, str]] = {}
        for rr in test_results[-1].iter(f"{XCCDF_NS}rule-result"):
            results[rr.get("idref") or ""] = (_text(rr.find(f"{XCCDF_NS}result")), rr.get("severity") or "unknown")

        counts = {r: 0 for r in RESULT_TYPES}
        for result, _ in results.values():
            counts[result] = counts.get(result, 0) + 1

        fixes = parse_fix_script(fix_file.read_text()) if fix_file and fix_file.is_file() else {}
        skipped = {short_rule_id(s) for s in skip_rules or []}

        findings = []
        for rule_id, (result, severity) in results.items():
            if result not in FINDING_RESULTS:
                continue
            rule = rules.get(rule_id)
            short = short_rule_id(rule_id)
            findings.append(
                Finding(
                    id=short,
                    title=_text(rule.find(f"{XCCDF_NS}title")) if rule is not None else "",
                    severity=severity,
                    result=result,
                    cis_refs=[
                        _text(ref)
                        for ref in (rule.iter(f"{XCCDF_NS}reference") if rule is not None else [])
                        if "cisecurity.org/benchmark" in (ref.get("href") or "")
                    ],
                    rationale=_text(rule.find(f"{XCCDF_NS}rationale")) if rule is not None else "",
                    fix_bash=fixes.get(short),
                    ignored=short in skipped,
                )
            )
        findings.sort(key=lambda f: (FINDING_RESULTS.index(f.result), -SEVERITY_RANK.get(f.severity, 0), f.id))

        arf_text = arf_file.read_text(encoding="utf-8") if arf_file and arf_file.is_file() else None
        checks = validate_scan(
            product=product,
            os_release=os_release,
            counts=counts,
            results={short_rule_id(k): v[0] for k, v in results.items()},
            arf_text=arf_text,
        )
        return cls(
            product=product,
            profile_id=profile_id,
            content=content,
            os_release=os_release,
            counts=counts,
            findings=findings,
            checks=checks,
        )

    def to_dict(self, target: ImageTarget, fail_on: FailOnEnum, status: str) -> dict:
        return {
            "image": target_metadata(target),
            "status": status,
            "content": self.content,
            "product": self.product,
            "profile": self.profile_id,
            "os_release": {k: self.os_release.get(k) for k in ("ID", "VERSION_ID", "NAME", "VERSION")},
            "validation": [asdict(c) for c in self.checks],
            "counts": self.counts,
            "failed_by_severity": self.severity_counts(),
            "gate": {"fail_on": fail_on.value, "breached": self.breached(fail_on)},
            "files": self.files,
            "findings": [asdict(f) for f in self.findings],
        }

    def to_markdown(self, target: ImageTarget, fail_on: FailOnEnum, status: str) -> str:
        lines = [
            f"# OpenSCAP results: {target}",
            "",
            f"- **Status:** {status}",
            f"- **Profile:** `{self.profile_id}`",
            f"- **Content:** {self.content} (`{self.product}`)",
            f"- **OS:** {self.os_release.get('NAME', '?')} {self.os_release.get('VERSION', '?')}",
            f"- **Gate:** `{fail_on.value}`",
            "",
            "| " + " | ".join(RESULT_TYPES) + " |",
            "|" + "---|" * len(RESULT_TYPES),
            "| " + " | ".join(str(self.counts.get(r, 0)) for r in RESULT_TYPES) + " |",
            "",
            "## Validation",
            "",
        ]
        lines += [f"- {'✅' if c.ok else '❌'} `{c.name}`: {c.detail}" for c in self.checks]
        lines += ["", "## Findings", ""]
        if not self.findings:
            lines.append("No failing, errored or unknown rules.")
        for f in self.findings:
            lines += [
                f"### `{f.id}` ({f.result}, {f.severity}){' (ignored)' if f.ignored else ''}",
                "",
                f"**{f.title}**",
                "",
            ]
            if f.cis_refs:
                lines += [f"CIS: {', '.join(f.cis_refs)}", ""]
            if f.rationale:
                lines += [f.rationale, ""]
            if f.fix_bash:
                lines += ["```bash", f.fix_bash, "```", ""]
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class OpenSCAPScanNotRun:
    """Recorded in place of a report when a target was skipped or its scan produced nothing usable."""

    verdict: str
    reason: str
    skipped: bool = False


def target_metadata(target: ImageTarget) -> dict:
    return {
        "name": target.image_name,
        "version": target.image_version.name,
        "variant": target.image_variant.name if target.image_variant else None,
        "os": target.image_os.name if target.image_os else None,
        "uid": target.uid,
    }


class OpenSCAPReportCollection(dict):
    """Reports keyed by image_name -> {uid: (target, report | OpenSCAPScanNotRun, status)}."""

    def add_report(self, target: ImageTarget, report: "OpenSCAPScanReport | OpenSCAPScanNotRun", status: str):
        self.setdefault(target.image_name, dict())[target.uid] = (target, report, status)

    def table(self) -> Table:
        table = Table(title="OpenSCAP Scan Results")
        for col in ("Image Name", "Version", "Variant", "OS", "Profile", "Status"):
            table.add_column(col, justify="left")
        for col, style in (
            ("Pass", "green"),
            ("Fail", "red"),
            ("Error", "bright_red"),
            ("Unknown", "yellow"),
            ("N/A", "bright_black"),
            ("High", "bright_red"),
            ("Med", "yellow"),
            ("Low", "bright_blue"),
        ):
            table.add_column(col, justify="right", header_style=style)

        for image_name, targets in self.items():
            for _, (target, report, status) in targets.items():
                meta = target_metadata(target)
                row = [image_name, meta["version"], meta["variant"] or "", meta["os"] or ""]
                status_style = "green" if status == "OK" else ("bright_black" if status == "SKIPPED" else "red bold")
                if isinstance(report, OpenSCAPScanNotRun):
                    row += ["", Text(f"{status}: {report.reason}", style=status_style)] + [
                        Text("-", style="bright_black italic")
                    ] * 8
                else:
                    sev = report.severity_counts()
                    row += [
                        report.profile_id.rsplit("_profile_", 1)[-1],
                        Text(status, style=status_style),
                        str(report.counts["pass"]),
                        str(report.counts["fail"]),
                        str(report.counts["error"]),
                        str(report.counts["unknown"]),
                        str(report.counts["notapplicable"]),
                        str(sev["high"]),
                        str(sev["medium"]),
                        str(sev["low"]),
                    ]
                table.add_row(*row)
        return table
