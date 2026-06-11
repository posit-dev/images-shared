from copy import deepcopy
from typing import Annotated, Literal

from pydantic import Field

from posit_bakery.config.tools.base import ToolOptions

DEFAULT_GOSS_TIMEOUT_SECONDS = 900  # 15 minutes


class GossOptions(ToolOptions):
    """Configuration options for Goss testing."""

    tool: Literal["goss"] = "goss"
    runtimeOptions: Annotated[
        str | None,
        Field(default=None, description="Additional runtime options to pass to dgoss.", examples=["--privileged"]),
    ] = None
    command: Annotated[str, Field(default="sleep infinity", description="Command to run in the dgoss container.")]
    wait: Annotated[
        int,
        Field(
            default=0,
            description="Time to wait before running tests, in seconds. Used as the value passed to the 'GOSS_SLEEP' "
            "environment variable.",
        ),
    ]
    timeout: Annotated[
        int,
        Field(
            default=DEFAULT_GOSS_TIMEOUT_SECONDS,
            description="Maximum seconds to allow a dgoss container to run before it is terminated. "
            "Set to 0 to disable the timeout.",
        ),
    ]

    def update(self, other: "GossOptions") -> "GossOptions":
        """Update this GossOptions instance with settings from another.

        The merge strategy is to use the values of the other instance if the value is not explicitly set in the current
        instance.
        """
        merged_options = deepcopy(self)
        if self.__pydantic_fields__["command"].default == self.command and "command" not in self.model_fields_set:
            merged_options.command = other.command
        if self.__pydantic_fields__["wait"].default == self.wait and "wait" not in self.model_fields_set:
            merged_options.wait = other.wait
        if (
            self.__pydantic_fields__["runtimeOptions"].default == self.runtimeOptions
            and "runtimeOptions" not in self.model_fields_set
        ):
            merged_options.runtimeOptions = other.runtimeOptions
        if self.__pydantic_fields__["timeout"].default == self.timeout and "timeout" not in self.model_fields_set:
            merged_options.timeout = other.timeout

        return merged_options
