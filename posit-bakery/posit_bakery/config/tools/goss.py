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
