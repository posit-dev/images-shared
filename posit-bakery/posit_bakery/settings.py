import logging
import os
import platform
import tempfile
from pathlib import Path

import typer

from posit_bakery.const import DEFAULT_MAX_CONCURRENCY


class Settings:
    """Application settings and paths."""

    def __init__(self):
        self.app_name = "bakery"
        self.application_storage: Path = Path(typer.get_app_dir(app_name=self.app_name)).resolve()
        self.temporary_storage: Path = Path(tempfile.gettempdir())
        self.log_level: str | int = logging.INFO
        self.architecture = self.get_host_architecture()
        self.max_concurrency: int = int(os.environ.get("BAKERY_MAX_CONCURRENCY", DEFAULT_MAX_CONCURRENCY))

    @staticmethod
    def get_host_architecture() -> str:
        """Returns the host architecture."""
        machine = platform.machine().lower()

        # Normalize common variants
        if machine in ("x86_64", "amd64"):
            return "amd64"
        elif machine in ("aarch64", "arm64"):
            return "arm64"
        elif machine.startswith("arm"):
            return "arm"
        else:
            return machine


SETTINGS = Settings()
