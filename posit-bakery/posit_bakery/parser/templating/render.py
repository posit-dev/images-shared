import os
import re
from enum import Enum
from pathlib import Path
from typing import Dict, Union

import git
import jinja2
import tomlkit
from rich import print
from tomlkit.items import AoT

from posit_bakery.error import BakeryTemplatingError
from posit_bakery.parser.templating.filters import regex_replace, jinja2_env
from posit_bakery.parser.templating.templates.configuration import (
    TPL_CONFIG_TOML,
    TPL_BASE_MANIFEST_TOML,
    TPL_PRODUCT_MANIFEST_TOML,
)
from posit_bakery.parser.templating.templates.containerfile import TPL_BASE_CONTAINERFILE, TPL_PRODUCT_CONTAINERFILE


class NewImageTypes(str, Enum):
    base = "base"
    product = "product"


def try_get_repo_url(context: Union[str, bytes, os.PathLike]) -> str:
    """Best guesses a repository URL for image labeling purposes based off the Git remote origin URL

    :param context: The repository root to check for a remote URL in
    :return: The guessed repository URL
    """
    url = "<REPLACE ME>"
    try:
        repo = git.Repo(context)
        # Use splitext since remotes should have `.git` as a suffix
        url = os.path.splitext(repo.remotes[0].config_reader.get("url"))[0]
        # If the URL is a git@ SSH URL, convert it to a https:// URL
        if url.startswith("git@"):
            url = url.removeprefix("git@")
            url = url.replace(":", "/")
        # TODO: There should be more logic around HTTPS URLs that may use `user@` prefixing
    except:  # noqa
        print("[bright_yellow][bold]WARNING:[/bold] Unable to determine repository name ")
    return url


def try_human_readable_os_name(os_name: str) -> str:
    """Attempts to convert an OS name to a human-readable format by splitting the name and version and capitalizing it

    :param os_name: The OS name to convert
    """
    p = re.compile(r"([a-zA-Z]+)([0-9.]+)")
    res = p.match(os_name).groups()
    return " ".join(res).title()


def create_new_image_directories(context: Union[str, bytes, os.PathLike], image_name: str) -> Path:
    """Creates an image directory structure for a new image in the provided context

    :param context: The root context directory to create the image directories in
    :param image_name: The name of the image to create directories for
    :return: The path to the new image directory
    """
    context = Path(context)
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


def render_new_image_template_files(
        context: Union[str, bytes, os.PathLike], image_name: str, image_type: str, image_base: str
) -> None:
    """Renders new template files for a new image in the provided context

    :param context: The root context directory to render new image templates in
    :param image_name: The name of the image
    :param image_type: The type of the image, either 'base' or 'product'
    :param image_base: The base image to use for the new image
    """
    context = Path(context)

    # Create directories for the new image if they don't exist
    image_path = create_new_image_directories(context, image_name)

    # Create a new config.toml file if it doesn't exist
    config_toml = context / "config.toml"
    if not config_toml.exists():
        tpl = jinja2.Environment(loader=jinja2.FileSystemLoader(context)).from_string(TPL_CONFIG_TOML)
        rendered = tpl.render(repo_url=try_get_repo_url(context))
        with open(config_toml, "w") as f:
            f.write(rendered)

    image_template_path = image_path / "template"

    # Choose the template to use based on the type of image being created
    # TODO: Remove concept of a "base" image
    if image_type == NewImageTypes.base:
        containerfile_tpl = TPL_BASE_CONTAINERFILE
        manifest_tpl = TPL_BASE_MANIFEST_TOML
    else:
        containerfile_tpl = TPL_PRODUCT_CONTAINERFILE
        manifest_tpl = TPL_PRODUCT_MANIFEST_TOML

    # Create a new manifest.toml file or raise an error if it already exists
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

    # Create a new Containerfile template if it doesn't exist
    containerfile_path = image_template_path / "Containerfile.jinja2"
    if not containerfile_path.exists():
        print(f"[bright_black]Creating new Containerfile template [bold]{containerfile_path}")
        tpl = jinja2.Environment().from_string(containerfile_tpl)
        rendered = tpl.render(image_name=image_name, base_image=image_base)
        with open(containerfile_path, "w") as f:
            f.write(rendered)


def create_new_image_version_directory(
        context: Union[str, bytes, os.PathLike], image_name: str, image_version: str
) -> Path:
    """Creates a new versioned directory for an image in the provided context

    :param context: The root context directory where the image is located
    :param image_name: The name of the image to create a versioned directory for
    :param image_version: The version of the image to create a directory for
    :return: The path to the new versioned image directory
    """
    context = Path(context)
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
    context: Union[str, bytes, os.PathLike],
    image_name: str,
    image_version: str,
    value_map: Dict[str, str],
    skip_render_minimal: bool = False,
):
    """Render templates into a new version of the image

    :param context: The root context directory where the image is located
    :param image_name: The name of the image to render templates for
    :param image_version: The version of the image to render templates for
    :param value_map: A dictionary of key-value pairs to pass to the templates for rendering
    :param skip_render_minimal: Skip rendering the minimal version of the Containerfile
    :return:
    """
    context = Path(context)
    image_template_path = context / image_name / "template"
    image_versioned_path = context / image_name / image_version

    # Create a Jinja2 environment with the template directory as the loader
    e = jinja2_env(
        loader=jinja2.FileSystemLoader(image_template_path),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
    )
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
    context: Union[str, bytes, os.PathLike],
    image_name: str,
    image_version: str,
    skip_mark_latest: bool = False,
) -> None:
    """Updates the build matrix in the manifest file for an image

    :param context: The root context directory where the image is located
    :param image_name: The name of the image to update the build matrix for
    :param image_version: The version of the image to add
    :param skip_mark_latest: Skip marking the version as latest
    """
    context = Path(context)
    image_path = context / image_name

    manifest_file = image_path / "manifest.toml"
    if not manifest_file.exists():
        print(f"[bright_red bold]ERROR:[/bold] Manifest file [bold]{manifest_file}[/bold] not found")
        raise BakeryTemplatingError(f"Manifest file '{manifest_file}' not found")
    with open(manifest_file, "r") as f:
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
            print(
                f"Unable to parse Containerfile os from {containerfile}. This may cause issues when rendering the build matrix."
            )
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
