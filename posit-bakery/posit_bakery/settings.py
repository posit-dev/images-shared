import tempfile
from pathlib import Path

import typer


class Settings:
    """Application settings and paths."""

    def __init__(self):
        self.app_name = "bakery"
        self.application_storage: Path = Path(typer.get_app_dir(app_name=self.app_name)).resolve()
        self.temporary_storage: Path = Path(tempfile.gettempdir())


SETTINGS = Settings()
