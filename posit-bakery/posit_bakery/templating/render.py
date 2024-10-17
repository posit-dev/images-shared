import os
import re
from enum import Enum
from pathlib import Path
from typing import Dict, List

import git
import hcl2
import jinja2
import tomlkit
from rich import print
from tomlkit.items import AoT

from posit_bakery.error import BakeryTemplatingError
from posit_bakery.templating import templates
from posit_bakery.templating.templates.configuration import CONFIG_TOML_TPL, BASE_MANIFEST_TOML_TPL, \
    PRODUCT_MANIFEST_TOML_TPL
from posit_bakery.templating.templates.containerfile import BASE_CONTAINER_FILE_TPL, PRODUCT_CONTAINER_FILE_TPL


class NewImageTypes(str, Enum):
    base = "base"
    product = "product"


def regex_replace(s, find, replace):
    return re.sub(find, replace, s)


def try_get_repo_url(context: Path):
    url = "<REPO_URL>"
    try:
        repo = git.Repo(context)
        url = os.path.splitext(repo.remotes[0].config_reader.get("url"))[0]
        if url.startswith("git@"):
            url = url.removeprefix("git@")
            url = url.replace(":", "/")
    except:
        print("[bright_yellow][bold]WARNING:[/bold] Unable to determine repository name ")
    return url


def try_human_readable_os_name(os: str):
    p = re.compile(r"([a-zA-Z]+)(0-9\.+)")
    res = p.match(os).groups()
    return " ".join(res)


def create_new_image_directories(context: Path, image_name: str) -> (Path, Path):
    if not context.exists():
        print(f"[bold bright_red]ERROR:[/bold red] Context path [bold]'{context}'[/bold] not found")
        raise BakeryTemplatingError(f"Context path '{context}' not found")

    image_path = context / image_name
    if not image_path.exists():
        print(f"[bright_black]Creating new image directory [bold]{image_path}")
        image_path.mkdir()

    image_template_path = image_path / "template"
    if not image_template_path.exists():
        print(f"[bright_black]Creating new image templates directory [bold]{image_template_path}")
        image_template_path.mkdir()

    image_test_path = image_template_path / "test"
    if not image_test_path.exists():
        print(f"[bright_black]Creating new image test templates directory [bold]{image_test_path}")
        image_test_path.mkdir()
    image_test_goss_file = image_test_path / "goss.yaml.jinja2"
    image_test_goss_file.touch(exist_ok=True)

    image_deps_path = image_template_path / "deps"
    if not image_deps_path.exists():
        print(f"[bright_black]Creating new image dependencies directory [bold]{image_deps_path}")
        image_deps_path.mkdir()
    image_deps_package_file = image_deps_path / "packages.txt.jinja2"
    image_deps_package_file.touch(exist_ok=True)

    return image_path


def render_new_image_template_files(context: Path, image_name: str, image_type: str, image_base: str):
    image_path = create_new_image_directories(context, image_name)

    config_toml = context / "config.toml"
    if not config_toml.exists():
        tpl = jinja2.Environment(loader=jinja2.FileSystemLoader(context)).from_string(CONFIG_TOML_TPL)
        rendered = tpl.render(repo_url=try_get_repo_url(context))
        with open(config_toml, "w") as f:
            f.write(rendered)

    image_template_path = image_path / "template"

    if image_type == NewImageTypes.base:
        containerfile_tpl = BASE_CONTAINER_FILE_TPL
        manifest_tpl = BASE_MANIFEST_TOML_TPL
    else:
        containerfile_tpl = PRODUCT_CONTAINER_FILE_TPL
        manifest_tpl = PRODUCT_MANIFEST_TOML_TPL

    manifest_toml = image_path / "manifest.toml"
    if manifest_toml.exists():
        print(f"[bright_red bold]ERROR:[/bold] Manifest file [bold]{manifest_toml}[/bold] already exists")
        raise BakeryTemplatingError(f"Manifest file '{manifest_toml}' already exists")
    else:
        print(f"[bright_black]Creating new manifest file [bold]{manifest_toml}")
        tpl = jinja2.Environment().from_string(manifest_tpl)
        rendered = tpl.render(image_name=image_name)
        with open(manifest_toml, "w") as f:
            f.write(rendered)

    containerfile_path = image_template_path / "Containerfile.jinja2"
    if not containerfile_path.exists():
        print(f"[bright_black]Creating new Containerfile template [bold]{containerfile_path}")
        tpl = jinja2.Environment().from_string(containerfile_tpl)
        rendered = tpl.render(image_name=image_name, base_image=image_base)
        with open(containerfile_path, "w") as f:
            f.write(rendered)


def create_new_image_version_directory(context: Path, image_name: str, image_version: str):
    image_path = context / image_name
    # Check if the image path exists and exit if it doesn't
    if not image_path.exists():
        print(f"[bright_red bold]ERROR:[/bold] Image path [bold]{image_path}[/bold] not found")
        raise BakeryTemplatingError(f"Image path '{image_path}' not found")
    # Check for a template directory under the provided image path and exit if it doesn't exist
    image_template_path = image_path / "template"
    if not image_template_path.exists():
        print(f"[bright_red bold]ERROR:[/bold] Image templates path [bold]{image_template_path}[/bold] not found")
        raise BakeryTemplatingError(f"Image templates path '{image_template_path}' not found")
    # Create a new versioned directory for the image if it doesn't exist
    image_versioned_path = image_path / image_version
    if not image_versioned_path.exists():
        print(f"[bright_black]Creating new directory [bold]{image_versioned_path}")
        image_versioned_path.mkdir()

    return image_versioned_path


def render_new_image_version_template_files(
        context: Path,
        image_name: str,
        image_version: str,
        value_map: Dict[str, str],
        skip_render_minimal: bool = False,
):
    image_template_path = context / image_name / "template"
    image_versioned_path = context / image_name / image_version

    # Create a Jinja2 environment with the template directory as the loader
    e = jinja2.Environment(
        loader=jinja2.FileSystemLoader(image_template_path),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
    )
    e.filters["regex_replace"] = regex_replace
    for tpl_rel_path in e.list_templates():
        tpl = e.get_template(tpl_rel_path)

        render_kwargs = {}
        if tpl_rel_path.startswith("Containerfile"):
            render_kwargs = {"trim_blocks": True}

        # If the template is a Containerfile, render it to both a minimal and standard version
        if tpl_rel_path.startswith("Containerfile") and not skip_render_minimal:
            containerfile_base_name = tpl_rel_path.removesuffix(".jinja2")
            rendered = tpl.render(image_version=image_version, **value_map, is_minimal=False, **render_kwargs)
            with open(image_versioned_path / f"{containerfile_base_name}.std", "w") as f:
                print(f"[bright_black]Rendering [bold]{image_versioned_path / f'{containerfile_base_name}.std'}")
                f.write(rendered)
            rendered_min = tpl.render(image_version=image_version, **value_map, is_minimal=True, **render_kwargs)
            with open(image_versioned_path / f"{containerfile_base_name}.min", "w") as f:
                print(f"[bright_black]Rendering [bold]{image_versioned_path / f'{containerfile_base_name}.min'}")
                f.write(rendered_min)
            continue
        rendered = tpl.render(image_version=image_version, **value_map, is_minimal=False, **render_kwargs)
        rel_path = tpl_rel_path.removesuffix(".jinja2")
        target_dir = Path(image_versioned_path / rel_path).parent
        target_dir.mkdir(parents=True, exist_ok=True)
        with open(image_versioned_path / rel_path, "w") as f:
            print(f"[bright_black]Rendering [bold]{image_versioned_path / rel_path}")
            f.write(rendered)


def update_manifest_build_matrix(
        context: Path,
        image_name: str,
        image_version: str,
        skip_mark_latest: bool = False,
):
    image_path = context / image_name

    manifest_file = image_path / "manifest.toml"
    if not manifest_file.exists():
        print(f"[bright_red bold]ERROR:[/bold] Manifest file [bold]{manifest_file}[/bold] not found")
        raise BakeryTemplatingError(f"Manifest file '{manifest_file}' not found")
    with open(manifest_file, 'r') as f:
        manifest = tomlkit.load(f)

    is_mono_os = manifest["const"].get("os", None) is not None

    image_versioned_path = image_path / image_version
    containerfiles = list(image_versioned_path.rglob("Containerfile*"))
    containerfiles = [str(containerfile.name).split(".") for containerfile in containerfiles]
    os_list = []
    target_list = []
    for containerfile in containerfiles:
        if len(containerfile) == 2 and is_mono_os:
            target_list.append(containerfile[1])
        elif len(containerfile) == 3 and not is_mono_os:
            os_list.append(containerfile[1])
            target_list.append(containerfile[2])
        else:
            print(f"Unable to parse Containerfile os from {containerfile}. This may cause issues when rendering the build matrix.")
    os_list = list(set(os_list))
    target_list = list(set(target_list))

    os_list = [try_human_readable_os_name(_os) for _os in os_list]

    builds = manifest["build"].unwrap()
    # If not skipping marking latest, mark all other versions as not latest
    if not skip_mark_latest:
        for build in builds:
            build["latest"] = False

    # Update the build matrix with the provided OS list and targets if the version already exists
    if any(image_version == build["version"] for build in builds):
        print(f"[bright_black]Replacing existing build entry for version '{image_version}'")
        for build in builds:
            if build["version"] == image_version:
                if os_list:
                    build["os"] = os_list
                if not skip_mark_latest:
                    build["latest"] = True
    # Otherwise, add a new entry to the build matrix
    else:
        print(f"[bright_black]Adding new build entry for version '{image_version}'")
        new_build = {
            "version": image_version,
        }
        if not is_mono_os:
            new_build["os"] = os_list or ["Ubuntu 22.04"]
        if target_list:
            new_build["targets"] = target_list
        if not skip_mark_latest:
            new_build["latest"] = True
        builds.insert(0, new_build)

    manifest["build"] = AoT(builds)

    with open(manifest_file, "w") as f:
        f.write(tomlkit.dumps(manifest))
