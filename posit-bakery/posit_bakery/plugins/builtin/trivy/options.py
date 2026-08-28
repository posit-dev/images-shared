from copy import deepcopy
from typing import Annotated, Literal

from pydantic import Field

from posit_bakery.config.tools.base import ToolOptions


class TrivyOptions(ToolOptions):
    """Configuration options for Trivy container image scanning."""

    tool: Literal["trivy"] = "trivy"
    severity: Annotated[
        list[str] | None,
        Field(default=None, description="Severities to report (e.g. HIGH, CRITICAL)."),
    ] = None
    failOnSeverity: Annotated[
        list[str] | None,
        Field(default=None, description="Severities that fail the scan if found. Unset means never fail."),
    ] = None
    disabledScanners: Annotated[
        list[str] | None,
        Field(default=None, description="Scanners to disable (e.g. secret, license, misconfig)."),
    ] = None
    timeout: Annotated[
        str | None,
        Field(default=None, description="Timeout for the scan (e.g. 1h, 10m)."),
    ] = None

    def update(self, other: "TrivyOptions") -> "TrivyOptions":
        """Update this instance with settings from another.

        The merge strategy uses the values of the other instance for any field not explicitly set
        in the current instance.
        """
        merged = deepcopy(self)
        for field_name in ("severity", "failOnSeverity", "disabledScanners", "timeout"):
            if field_name not in self.model_fields_set:
                setattr(merged, field_name, getattr(other, field_name))
        return merged
