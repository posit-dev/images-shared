import logging
from copy import copy
from pathlib import Path
from typing import Any, Dict, List

import jinja2

import posit_bakery.util as util
from posit_bakery.error import BakeryTemplatingError, BakeryFileError
from posit_bakery.templating import TPL_CONFIG_TOML, TPL_MANIFEST_TOML, TPL_CONTAINERFILE
from posit_bakery.templating.filters import jinja2_env

log = logging.getLogger(__name__)


def create_project_config(context: Path) -> None:
    if not context.is_dir():
        log.error(f"Context directory does not exist: [bold]{context}")
        raise BakeryFileError(f"Project directory does not exist.", context)

    config_file = context / "config.toml"
    if not config_file.is_file():
        log.info(f"Creating new project config file [bold]{config_file}")
        tpl = jinja2.Environment(loader=jinja2.FileSystemLoader(context)).from_string(TPL_CONFIG_TOML)
        rendered = tpl.render(repo_url=util.try_get_repo_url(context))
        with open(config_file, "w") as f:
            f.write(rendered)


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


def render_image_templates(context: Path, version: str, template_values: Dict[str, Any], targets: List[str]) -> None:
    image_context: Path = context.parent
    project_context: Path = image_context.parent

    image_template_path: Path = image_context / "template"
    if not image_template_path.is_dir():
        raise BakeryTemplatingError(f"Image templates to not exist in [bold]{image_template_path}")

    exists: bool = context.is_dir()
    if not exists:
        log.debug(f"Creating new image version directory [bold]{context}")
        context.mkdir()

    # Initialize the value map with relative path
    value_map: Dict[str, Any] = copy(template_values)
    if "rel_path" not in value_map:
        value_map["rel_path"] = context.relative_to(project_context)

    e = jinja2_env(
        loader=jinja2.FileSystemLoader(image_template_path), autoescape=True, undefined=jinja2.StrictUndefined
    )
    # Line failing
    for tpl_rel_path in e.list_templates():
        tpl = e.get_template(tpl_rel_path)

        render_kwargs = {}
        if tpl_rel_path.startswith("Containerfile"):
            render_kwargs["trim_blocks"] = True

        # If the template is a Containerfile, render it to both a minimal and standard version
        if tpl_rel_path.startswith("Containerfile"):
            containerfile_base_name = tpl_rel_path.removesuffix(".jinja2")
            for image_type in targets:
                containerfile: Path = context / f"{containerfile_base_name}.{image_type}"
                rendered = tpl.render(image_version=version, **value_map, image_type=image_type, **render_kwargs)
                with open(containerfile, "w") as f:
                    log.debug(f"Rendering [bold]{containerfile}")
                    f.write(rendered)
                continue
        else:
            rendered = tpl.render(image_version=version, **value_map, **render_kwargs)
            rel_path = tpl_rel_path.removesuffix(".jinja2")
            output_file = context / rel_path
            (output_file.parent).mkdir(parents=True, exist_ok=True)
            with open(context / rel_path, "w") as f:
                log.debug(f"[bright_black]Rendering [bold]{output_file}")
                f.write(rendered)
