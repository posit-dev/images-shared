from enum import Enum
from pathlib import Path
from typing import Dict

import hcl2
import jinja2

from posit_bakery.error import BakeryTemplatingError
from posit_bakery.templating import base_templates, product_templates


class NewImageTypes(str, Enum):
    base = "base"
    product = "product"


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
    image_test_goss_file = image_test_path / "goss.yaml"
    image_test_goss_file.touch(exist_ok=True)

    image_deps_path = image_template_path / "deps"
    if not image_deps_path.exists():
        print(f"[bright_black]Creating new image dependencies directory [bold]{image_deps_path}")
        image_deps_path.mkdir()
    image_deps_package_file = image_deps_path / "packages.txt"
    image_deps_package_file.touch(exist_ok=True)

    return image_path


def render_new_image_template_files(image_name: str, image_type: str, image_base: str, image_path: Path):
    image_template_path = image_path / "template"

    if image_type == NewImageTypes.base:
        template_module = base_templates
    else:
        template_module = product_templates

    bake_file_path = image_path / "docker-bake.hcl"
    if not bake_file_path.exists():
        print(f"[bright_black]Creating new docker-bake file [bold]{bake_file_path}")
        tpl = jinja2.Environment().from_string(template_module.DOCKER_BAKE_TPL)
        rendered = tpl.render(image_name=image_name, base_image=image_base)
        with open(bake_file_path, "w") as f:
            f.write(rendered)

    containerfile_path = image_template_path / "Containerfile.jinja2"
    if not containerfile_path.exists():
        print(f"[bright_black]Creating new Containerfile template [bold]{containerfile_path}")
        tpl = jinja2.Environment().from_string(template_module.CONTAINER_FILE_TPL)
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
        undefined=jinja2.StrictUndefined
    )
    for tpl_rel_path in e.list_templates():
        tpl = e.get_template(tpl_rel_path)

        # If the template is a Containerfile, render it to both a minimal and standard version
        if tpl_rel_path.startswith("Containerfile") and not skip_render_minimal:
            containerfile_base_name = tpl_rel_path.removesuffix(".jinja2")
            rendered = tpl.render(image_version=image_version, **value_map, is_minimal=False)
            with open(image_versioned_path / f"{containerfile_base_name}.std", "w") as f:
                print(f"[bright_black]Rendering [bold]{image_versioned_path / f'{containerfile_base_name}.std'}")
                f.write(rendered)
            rendered_min = tpl.render(image_version=image_version, **value_map, is_minimal=True)
            with open(image_versioned_path / f"{containerfile_base_name}.min", "w") as f:
                print(f"[bright_black]Rendering [bold]{image_versioned_path / f'{containerfile_base_name}.min'}")
                f.write(rendered_min)
            continue
        rendered = tpl.render(image_version=image_version, **value_map, is_minimal=False)
        rel_path = tpl_rel_path.removesuffix(".jinja2")
        target_dir = Path(image_versioned_path / rel_path).parent
        target_dir.mkdir(parents=True, exist_ok=True)
        with open(image_versioned_path / rel_path, "w") as f:
            print(f"[bright_black]Rendering [bold]{image_versioned_path / rel_path}")
            f.write(rendered)


def regenerate_build_matrix(
        context: Path,
        image_name: str,
        image_version: str,
        skip_render_minimal: bool = False,
        skip_mark_latest: bool = False,
):
    image_path = context / image_name
    image_versioned_path = image_path / image_version
    containerfiles = list(image_versioned_path.rglob("Containerfile*"))
    containerfiles = [str(containerfile.name).split(".") for containerfile in containerfiles]
    os_list = []
    for containerfile in containerfiles:
        if (len(containerfile) == 2 and skip_render_minimal) or len(containerfile) == 3:
            os_list.append(containerfile[1])
        else:
            print(f"Unable to parse Containerfile os from {containerfile}. This may cause issues when rendering the build matrix.")
    os_list = list(set(os_list))

    matrix_file = image_path / "docker-bake.matrix.hcl"
    if not matrix_file.exists():
        print(f"[bright_red bold]ERROR:[/bold] Matrix file [bold]{matrix_file}[/bold] not found")
        raise BakeryTemplatingError(f"Matrix file '{matrix_file}' not found")
    # Get OS extensions from Containerfiles
    matrix_template = """variable build_matrix {
    default = {
        builds = [
            {% for build in build_versions -%}
            {version = "{{ build.version }}", {% if build.os %}os = "{{ build.os }}",{% endif %} mark_latest = {{ build.latest }}},
            {% endfor -%}
        ]
    }
}
"""
    matrix_builds = []
    if os_list:
        for os in os_list:
            matrix_builds.append({"version": image_version, "os": os, "latest": str(not skip_mark_latest).lower()})
    else:
        matrix_builds = [{"version": image_version, "os": None, "latest": str(not skip_mark_latest).lower()}]
    with open(matrix_file, 'r') as f:
        matrix_content = hcl2.load(f)
    for build in matrix_content["variable"][0]["build_matrix"]["default"]["builds"]:
        mark_latest = "false"
        if skip_mark_latest:
            mark_latest = build["mark_latest"]
        if build["version"] == "" or matrix_builds[0]["version"] == build["version"]:
            continue
        matrix_builds.append({"version": build["version"], "os": build.get("os"), "latest": mark_latest})

    tpl = jinja2.Environment().from_string(matrix_template)
    rendered = tpl.render(build_versions=matrix_builds)
    with open(matrix_file, "w") as f:
        f.write(rendered)
