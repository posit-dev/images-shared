import re
from copy import deepcopy
from typing import Annotated, Literal

from pydantic import Field, field_validator

from posit_bakery.config.tools.base import ToolOptions

# Severity buckets TrivyScanReport counts (report.py); anything else can never breach.
VALID_SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")

_GO_DURATION_RE = re.compile(r"^(\d+(\.\d+)?(ns|us|µs|ms|s|m|h))+$")


def parse_severities(values: list[str]) -> list[str]:
    """Strip and upper-case severity names, rejecting empty lists and unknown names."""
    normalised = [v.strip().upper() for v in values]
    if not normalised:
        raise ValueError("severity list must not be empty; omit it to fall back to trivy's exit code")
    invalid = [v for v in normalised if v not in VALID_SEVERITIES]
    if invalid:
        raise ValueError(f"unknown severities {invalid}; expected any of {list(VALID_SEVERITIES)}")
    return normalised


def validate_timeout(value: str) -> str:
    """Reject anything that is not a Go duration (e.g. 5m0s), which trivy would reject mid-scan."""
    if not _GO_DURATION_RE.fullmatch(value):
        raise ValueError(f"invalid timeout {value!r}; expected a Go duration such as '5m0s'")
    return value


class TrivyOptions(ToolOptions):
    """Configuration options for Trivy container image scanning."""

    tool: Literal["trivy"] = "trivy"
    severity: Annotated[
        list[str] | None,
        Field(default=None, description="Severities to scan for (e.g. CRITICAL, HIGH)."),
    ] = None
    ignoreUnfixed: Annotated[
        bool | None,
        Field(default=None, description="Ignore vulnerabilities without an available fix."),
    ] = None
    skipFiles: Annotated[
        list[str] | None,
        Field(default=None, description="File paths to skip during scanning."),
    ] = None
    skipDirs: Annotated[
        list[str] | None,
        Field(default=None, description="Directory paths to skip during scanning."),
    ] = None
    exitCode: Annotated[
        int | None,
        Field(default=None, description="Exit code trivy returns when vulnerabilities are found."),
    ] = None
    scanners: Annotated[
        list[str] | None,
        Field(default=None, description="Trivy scanner types to enable (e.g. vuln, secret, misconfig, license)."),
    ] = None
    timeout: Annotated[
        str | None,
        Field(default=None, description="Timeout for the scan (e.g. 5m0s)."),
    ] = None
    failureSeverity: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="Severities that fail the build when present in the parsed report. Must be a subset of "
            "`severity` when that is set, since trivy only reports the severities it scans. "
            "When unset, falls back to trivy's own exit code.",
        ),
    ] = None

    @field_validator("failureSeverity")
    @classmethod
    def _normalise_failure_severity(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else parse_severities(value)

    @field_validator("timeout")
    @classmethod
    def _check_timeout(cls, value: str | None) -> str | None:
        return None if value is None else validate_timeout(value)

    def update(self, other: "TrivyOptions") -> "TrivyOptions":
        """Update this instance with settings from another.

        The merge strategy uses the values of the other instance for any field not explicitly set
        in the current instance.
        """
        merged = deepcopy(self)
        for field_name in (
            "severity",
            "ignoreUnfixed",
            "skipFiles",
            "skipDirs",
            "exitCode",
            "scanners",
            "timeout",
            "failureSeverity",
        ):
            if field_name not in self.model_fields_set:
                setattr(merged, field_name, getattr(other, field_name))
        return merged
