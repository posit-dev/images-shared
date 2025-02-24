import os
from pathlib import Path

TEMPLATE_DIR: Path = Path(os.path.dirname(os.path.realpath(__file__))) / "templates"

TPL_CONFIG_TOML = (TEMPLATE_DIR / "config.toml.jinja2").read_text()
TPL_MANIFEST_TOML = (TEMPLATE_DIR / "manifest.toml.jinja2").read_text()
TPL_CONTAINERFILE = (TEMPLATE_DIR / "containerfile.jinja2").read_text()
