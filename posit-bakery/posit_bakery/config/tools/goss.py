from copy import deepcopy
from typing import Annotated, Literal

from pydantic import Field

from posit_bakery.config.tools.base import ToolOptions


class GossOptions(ToolOptions):
    """Configuration options for Goss testing."""

    tool: Literal["goss"] = "goss"
    command: Annotated[str, Field(default="sleep infinity", description="Command to run in the dgoss container.")]
    wait: Annotated[
        int,
        Field(
            default=0,
            description="Time to wait before running tests, in seconds. Used as the value passed to the 'GOSS_SLEEP' "
            "environment variable.",
        ),
    ]

    def merge(self, other: "GossOptions") -> "GossOptions":
        """Merge another GossOptions instance into this one.

        The merge strategy is to use the values of the other instance if they are not set to defaults and the value is
        not explicitly set in the current instance.
        """
        merged_options = deepcopy(self)
        if (
            self.model_fields["command"].default == self.command
            and self.model_fields["command"].default != other.command
            and "command" not in self.model_fields_set
        ):
            merged_options.command = other.command
        if (
            self.model_fields["wait"].default == self.wait
            and self.model_fields["wait"].default != other.wait
            and "wait" not in self.model_fields_set
        ):
            merged_options.wait = other.wait

        return merged_options
