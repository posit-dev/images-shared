import os
from pathlib import Path

from posit_bakery.config.templating.render import jinja2_env, render_template

TEMPLATE_DIR: Path = Path(os.path.dirname(os.path.realpath(__file__))) / "templates"

TPL_BAKERY_CONFIG_YAML = (TEMPLATE_DIR / "bakery.yaml.jinja2").read_text()
TPL_CONTAINERFILE = (TEMPLATE_DIR / "Containerfile.jinja2").read_text()

__all__ = [
    "TEMPLATE_DIR",
    "TPL_BAKERY_CONFIG_YAML",
    "TPL_CONTAINERFILE",
    "jinja2_env",
    "render_template",
]
