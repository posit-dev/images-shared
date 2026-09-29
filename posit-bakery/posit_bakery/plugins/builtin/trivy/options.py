from copy import deepcopy
from typing import Annotated, Literal

from pydantic import Field

from posit_bakery.config.tools.base import ToolOptions


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

    def update(self, other: "TrivyOptions") -> "TrivyOptions":
        """Update this instance with settings from another.

        The merge strategy uses the values of the other instance for any field not explicitly set
        in the current instance.
        """
        merged = deepcopy(self)
        for field_name in ("severity", "ignoreUnfixed", "skipFiles", "skipDirs", "exitCode"):
            if field_name not in self.model_fields_set:
                setattr(merged, field_name, getattr(other, field_name))
        return merged
