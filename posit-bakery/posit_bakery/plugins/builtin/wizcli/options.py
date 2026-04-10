from copy import deepcopy
from typing import Annotated, Literal

from pydantic import Field

from posit_bakery.config.tools.base import ToolOptions


class WizCLIOptions(ToolOptions):
    """Configuration options for WizCLI container image scanning."""

    tool: Literal["wizcli"] = "wizcli"
    projects: Annotated[
        list[str] | None,
        Field(default=None, description="Wiz project IDs or slugs to scope the scan to."),
    ] = None
    policies: Annotated[
        list[str] | None,
        Field(default=None, description="Policies to apply to the scan."),
    ] = None
    tags: Annotated[
        list[str] | None,
        Field(default=None, description="Tags to mark the scan with (KEY or KEY=VALUE)."),
    ] = None
    scanOsManagedLibraries: Annotated[
        bool | None,
        Field(default=None, description="Enable or disable scanning of OS-package managed code libraries."),
    ] = None
    scanGoStandardLibrary: Annotated[
        bool | None,
        Field(default=None, description="Enable or disable scanning of Go standard library."),
    ] = None

    def update(self, other: "WizCLIOptions") -> "WizCLIOptions":
        """Update this instance with settings from another.

        The merge strategy uses the values of the other instance for any field not explicitly set
        in the current instance.
        """
        merged = deepcopy(self)
        for field_name in ("projects", "policies", "tags", "scanOsManagedLibraries", "scanGoStandardLibrary"):
            if field_name not in self.model_fields_set:
                setattr(merged, field_name, getattr(other, field_name))
        return merged
