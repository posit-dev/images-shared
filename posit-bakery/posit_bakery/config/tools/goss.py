from typing import Annotated, Literal

from pydantic import Field

from posit_bakery.config.tools.base import ToolOptions


class GossOptions(ToolOptions):
    tool: Literal["goss"] = "goss"
    command: Annotated[str, Field(default="sleep infinity")]
    wait: Annotated[int, Field(default=0)]
