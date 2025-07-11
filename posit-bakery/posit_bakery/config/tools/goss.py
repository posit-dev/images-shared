from typing import Annotated

from pydantic import Field

from posit_bakery.config.tools.base import ToolOptions


class GossOptions(ToolOptions):
    name: Annotated[str, Field(default="goss")]
    command: Annotated[str, Field(default="sleep infinity")]
    wait: Annotated[int, Field(default=0)]
