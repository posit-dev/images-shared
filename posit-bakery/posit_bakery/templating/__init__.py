import os
from pathlib import Path

TEMPLATE_DIR: Path = Path(os.path.dirname(os.path.realpath(__file__))) / "templates"

TPL_CONFIG_TOML = open(TEMPLATE_DIR / "config.toml.jinja2").read()
TPL_MANIFEST_TOML = open(TEMPLATE_DIR / "manifest.toml.jinja2").read()
TPL_CONTAINERFILE = open(TEMPLATE_DIR / "containerfile.jinja2").read()
