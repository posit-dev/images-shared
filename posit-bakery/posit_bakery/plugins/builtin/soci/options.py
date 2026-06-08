from copy import deepcopy
from enum import Enum
from typing import Annotated, Literal

from pydantic import Field

from posit_bakery.config.tools.base import ToolOptions


class SociModeEnum(str, Enum):
    """SOCI conversion mode selected on the CLI."""

    CONTAINERD = "containerd"
    STANDALONE = "standalone"


class SociOptions(ToolOptions):
    """Configuration options for SOCI indexing."""

    tool: Literal["soci"] = "soci"
    enabled: Annotated[
        bool,
        Field(default=False, description="Enable SOCI conversion for this image."),
    ]
    span_size: Annotated[
        int | None,
        Field(default=None, description="SOCI zTOC span size in bytes. SOCI default if None."),
    ]
    min_layer_size: Annotated[
        int | None,
        Field(default=None, description="Minimum layer size to index. SOCI default if None."),
    ]
    prefetch_files: Annotated[
        list[str],
        Field(default_factory=list, description="Files to mark for prefetch in the SOCI index."),
    ]
    optimizations: Annotated[
        list[str],
        Field(default_factory=list, description="Optional optimizations (e.g. 'xattr')."),
    ]
    platforms: Annotated[
        list[str] | None,
        Field(default=None, description="Platforms to convert. None => --all-platforms."),
    ]

    def update(self, other: "SociOptions") -> "SociOptions":
        """Update this SociOptions instance with settings from another.

        The merge strategy is to use the values of the other instance if the value is not explicitly set in the current
        instance.
        """
        merged = deepcopy(self)
        for field_name in (
            "enabled",
            "span_size",
            "min_layer_size",
            "prefetch_files",
            "optimizations",
            "platforms",
        ):
            if field_name not in self.model_fields_set:
                setattr(merged, field_name, getattr(other, field_name))
        return merged
