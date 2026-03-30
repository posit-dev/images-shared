from typing import Protocol, Any

import typer
from pydantic import BaseModel

from posit_bakery.image import ImageTarget


class ToolCallResult(BaseModel):
    """Represent the result of a tool call."""

    exit_code: int
    tool_name: str
    target: ImageTarget
    stdout: str
    stderr: str
    artifacts: dict[str, Any] | None = None


class BakeryToolPlugin(Protocol):
    name: str
    description: str

    def register_cli(self, app: typer.Typer) -> None:
        """Register the plugin's CLI commands with the given Typer app."""
        ...


    def execute(self, targets: list[ImageTarget], **kwargs):
        """Execute the plugin's tools against the given ImageTarget objects."""
        ...
