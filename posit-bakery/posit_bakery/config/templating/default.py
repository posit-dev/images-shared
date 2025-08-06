import logging
from pathlib import Path

import jinja2

import posit_bakery.util as util
from posit_bakery.config.templating import TPL_BAKERY_CONFIG_YAML, TPL_CONTAINERFILE
from posit_bakery.config.templating.filters import jinja2_env

log = logging.getLogger(__name__)


def create_project_config(config_file: Path) -> None:
    log.info(f"Creating new project config file [bold]{config_file}")
    tpl = jinja2_env(loader=jinja2.FileSystemLoader(config_file.parent)).from_string(TPL_BAKERY_CONFIG_YAML)
    rendered = tpl.render(repo_url=util.try_get_repo_url(config_file.parent))
    with open(config_file, "w") as f:
        f.write(rendered)


def create_image_templates(image_path: Path, image_name: str, base_tag: str):
    exists: bool = image_path.is_dir()
    if not exists:
        log.debug(f"Creating new image directory [bold]{image_path}")
        image_path.mkdir()

    image_template_path = image_path / "template"
    if not image_template_path.is_dir():
        log.debug(f"Creating new image templates directory [bold]{image_template_path}")
        image_template_path.mkdir()

    # Create a new Containerfile template if it doesn't exist
    containerfile_path = image_template_path / "Containerfile.jinja2"
    if not containerfile_path.is_file():
        log.debug(f"Creating new Containerfile template [bold]{containerfile_path}")
        tpl = jinja2_env().from_string(TPL_CONTAINERFILE)
        rendered = tpl.render(image_name=image_name, base_tag=base_tag)
        with open(containerfile_path, "w") as f:
            f.write(rendered)

    image_test_path = image_template_path / "test"
    if not image_test_path.is_dir():
        log.debug(f"Creating new image templates test directory [bold]{image_test_path}")
        image_test_path.mkdir()
    image_test_goss_file = image_test_path / "goss.yaml.jinja2"
    image_test_goss_file.touch(exist_ok=True)

    image_deps_path = image_template_path / "deps"
    if not image_deps_path.is_dir():
        log.debug(f"Creating new image templates dependencies directory [bold]{image_deps_path}")
        image_deps_path.mkdir()
    image_deps_package_file = image_deps_path / "packages.txt.jinja2"
    image_deps_package_file.touch(exist_ok=True)
