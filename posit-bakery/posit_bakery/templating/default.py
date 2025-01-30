import logging
from pathlib import Path

import jinja2

from posit_bakery.error import BakeryTemplatingError
from posit_bakery.templating import TPL_MANIFEST_TOML, TPL_CONTAINERFILE

log = logging.getLogger("rich")


def create_image_templates(context: Path, image_name: str, base_tag: str) -> None:
    exists: bool = context.is_dir()
    if not exists:
        log.debug(f"Creating new image directory [bold]{context}")
        context.mkdir()

    manifest_file = context / "manifest.toml"
    if manifest_file.is_file():
        log.error(f"Manifest file [bold]{manifest_file}[/bold] already exists")
        raise BakeryTemplatingError(f"Manifest file '{manifest_file}' already exists. Please remove it first.")
    else:
        log.debug(f"Creating new manifest file [bold]{manifest_file}")
        tpl = jinja2.Environment().from_string(TPL_MANIFEST_TOML)
        rendered = tpl.render(image_name=image_name)
        with open(manifest_file, "w") as f:
            f.write(rendered)

    image_template_path = context / "template"
    if not image_template_path.is_dir():
        log.debug(f"Creating new image templates directory [bold]{image_template_path}")
        image_template_path.mkdir()

    # Create a new Containerfile template if it doesn't exist
    containerfile_path = image_template_path / "Containerfile.jinja2"
    if not containerfile_path.is_file():
        log.debug(f"Creating new Containerfile template [bold]{containerfile_path}")
        tpl = jinja2.Environment().from_string(TPL_CONTAINERFILE)
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
