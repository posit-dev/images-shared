from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import typer
from pydantic import BaseModel

from posit_bakery.image.image_target import ImageTarget


class ToolCallResult(BaseModel):
    """Represent the result of a tool call."""

    exit_code: int
    tool_name: str
    target: ImageTarget
    stdout: str
    stderr: str
    artifacts: dict[str, Any] | None = None


@runtime_checkable
class BakeryToolPlugin(Protocol):
    name: str
    description: str

    def register_cli(self, app: typer.Typer) -> None:
        """Register the plugin's CLI commands with the given Typer app."""
        ...

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        platform: str | None = None,
        **kwargs,
    ) -> list[ToolCallResult]:
        """Execute the plugin's tools against the given ImageTarget objects."""
        ...
