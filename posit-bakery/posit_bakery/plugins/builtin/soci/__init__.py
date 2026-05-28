"""SOCI plugin: convert built images into SOCI-enabled images."""

import logging
from pathlib import Path

import typer

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.soci.options import SociOptions
from posit_bakery.plugins.protocol import BakeryToolPlugin, ToolCallResult

log = logging.getLogger(__name__)


class SociPlugin(BakeryToolPlugin):
    name: str = "soci"
    description: str = "Convert images to SOCI-enabled images"
    tool_options_class = SociOptions

    def register_cli(self, app: typer.Typer) -> None:
        """Register the soci CLI commands. Filled in in a later task."""
        soci_app = typer.Typer(no_args_is_help=True)
        app.add_typer(soci_app, name="soci", help=self.description)

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        **kwargs,
    ) -> list[ToolCallResult]:
        """Execute SOCI conversion. Filled in in a later task."""
        return []

    def results(self, results: list[ToolCallResult]) -> None:
        """Display SOCI results. Filled in in a later task."""
        return
