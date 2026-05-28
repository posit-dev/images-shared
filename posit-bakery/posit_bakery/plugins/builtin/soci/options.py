from typing import Literal

from posit_bakery.config.tools.base import ToolOptions


class SociOptions(ToolOptions):
    """Configuration options for SOCI indexing. Filled in in a later task."""

    tool: Literal["soci"] = "soci"

    def update(self, other: "SociOptions") -> "SociOptions":
        """Update this SociOptions instance with settings from another.

        The merge strategy is to use the values of the other instance if the value is not explicitly set in the current
        instance.
        """
        # Placeholder implementation for now. Actual merging logic will be filled in later tasks.
        return self
