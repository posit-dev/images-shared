import tempfile
from pathlib import Path

import typer

APP_NAME = "bakery"
APP_DIRECTORY: Path = Path(typer.get_app_dir(APP_NAME)).resolve()
TEMP_DIRECTORY: Path = Path(tempfile.gettempdir())
