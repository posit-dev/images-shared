from copy import deepcopy
from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, field_validator

from posit_bakery.config.tools.base import ToolOptions

DEFAULT_PROFILE = "cis_level1_server"
BUILTIN_CONTAINER_TAILORING = "builtin:container"
NO_TAILORING = "none"


class FailOnEnum(str, Enum):
    NONE = "none"
    ANY = "any"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OutputFormatEnum(str, Enum):
    TABLE = "table"
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"
    XCCDF = "xccdf"
    ARF = "arf"
    FIX = "fix"


DEFAULT_FORMATS = [OutputFormatEnum.TABLE, OutputFormatEnum.JSON, OutputFormatEnum.HTML]


def parse_formats(values: list[str]) -> list[OutputFormatEnum]:
    """Normalise and validate output format names."""
    normalised = [v.strip().lower() for v in values if v.strip()]
    if not normalised:
        raise ValueError("format list must not be empty")
    valid = [f.value for f in OutputFormatEnum]
    invalid = [v for v in normalised if v not in valid]
    if invalid:
        raise ValueError(f"unknown formats {invalid}; expected any of {valid}")
    return [OutputFormatEnum(v) for v in normalised]


class OpenSCAPOptions(ToolOptions):
    """Configuration options for OpenSCAP CIS benchmark scans."""

    tool: Literal["openscap"] = "openscap"
    profile: Annotated[
        str | None,
        Field(
            default=None,
            description="XCCDF profile short name (e.g. cis_level1_server) or full ID. "
            f"Defaults to `{DEFAULT_PROFILE}`.",
        ),
    ] = None
    contentVersion: Annotated[
        str | None,
        Field(default=None, description="ComplianceAsCode (SCAP Security Guide) release to scan with."),
    ] = None
    datastream: Annotated[
        str | None,
        Field(default=None, description="Path or URL to an SCAP datastream, overriding OS-based content selection."),
    ] = None
    tailoring: Annotated[
        str | None,
        Field(
            default=None,
            description=f"Path or URL to an XCCDF tailoring file, `{BUILTIN_CONTAINER_TAILORING}` (default) to "
            f"exclude host/kernel-only rules, or `{NO_TAILORING}`.",
        ),
    ] = None
    skipRules: Annotated[
        list[str] | None,
        Field(default=None, description="Rule IDs ignored for gating. They are still reported as ignored."),
    ] = None
    failOn: Annotated[
        FailOnEnum | None,
        Field(default=None, description="Minimum failing-rule severity that fails the run. Defaults to `none`."),
    ] = None
    formats: Annotated[
        list[OutputFormatEnum] | None,
        Field(default=None, description="Output formats to produce. Defaults to table, json and html."),
    ] = None

    @field_validator("formats", mode="before")
    @classmethod
    def _check_formats(cls, value):
        return None if value is None else parse_formats([str(getattr(v, "value", v)) for v in value])

    def update(self, other: "OpenSCAPOptions") -> "OpenSCAPOptions":
        """Use the other instance's values for any field not explicitly set on this one."""
        merged = deepcopy(self)
        for field_name in ("profile", "contentVersion", "datastream", "tailoring", "skipRules", "failOn", "formats"):
            if field_name not in self.model_fields_set:
                setattr(merged, field_name, getattr(other, field_name))
        return merged
