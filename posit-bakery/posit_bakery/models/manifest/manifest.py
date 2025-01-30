import logging
import os
import re

from pathlib import Path
from typing import Dict, Union, List

import jinja2

from posit_bakery.error import BakeryFileNotFoundError
from posit_bakery.models.generic import GenericTOMLModel
from posit_bakery.models.manifest.document import ManifestDocument
from posit_bakery.templating.filters import render_template, condense, tag_safe, clean_version, jinja2_env


log = logging.getLogger("rich")


class Manifest(GenericTOMLModel):
    """Simple wrapper around an image manifest.toml file"""

    @classmethod
    def load(cls, filepath: Union[str, bytes, os.PathLike]) -> "Manifest":
        """Load a Config object from a TOML file

        :param filepath: Path to the config.toml file
        """
        filepath = Path(filepath)
        document = cls.read(filepath)
        model = ManifestDocument(**document.unwrap())

        return cls(filepath=filepath, context=filepath.parent, document=document, model=model)

    @property
    def image_name(self) -> str:
        return str(self.model.image_name)

    @property
    def types(self) -> List[str]:
        """Get the target types present in the target builds"""
        return [_type for _type in self.model.target.keys()]

    @property
    def versions(self) -> List[str]:
        """Get the build versions present in the target builds"""
        return [version for version in self.model.build.keys()]

    @staticmethod
    def guess_image_os_list(p: Path) -> List[str]:
        """Guess the operating systems for an image based on the Containerfile extensions present in the image directory

        :param p: Path to the versioned image directory containing Containerfiles to guess OSes from
        """
        os_list = []
        pat = re.compile(r"Containerfile\.([a-zA-Z]+)([0-9.]+)\.[a-zA-Z0-9]")
        containerfiles = list(p.glob("Containerfile*"))
        containerfiles = [str(containerfile.relative_to(p)) for containerfile in containerfiles]
        for containerfile in containerfiles:
            match = pat.match(containerfile)
            if match:
                os_list.append(" ".join(match.groups()).title())
        os_list = list(set(os_list))
        return os_list

    def render_image_template(self, version: str, value_map: Dict[str, str] = None) -> None:
        """Render the image template files for a new version

        :param version: Version to render the image template files for
        :param value_map: Map of values to use in the template rendering
        """
        template_directory = self.context / "template"
        if not template_directory.is_dir():
            raise BakeryFileNotFoundError(f"Path '{self.context}/template' does not exist.")
        new_directory = self.context / version
        new_directory.mkdir(exist_ok=True)

        if value_map is None:
            value_map = {}
        if "rel_path" not in value_map:
            value_map["rel_path"] = new_directory.relative_to(self.config.context)

        e = jinja2_env(
            loader=jinja2.FileSystemLoader(template_directory), autoescape=True, undefined=jinja2.StrictUndefined
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
                for image_type in self.types:
                    rendered = tpl.render(image_version=version, **value_map, image_type=image_type, **render_kwargs)
                    with open(new_directory / f"{containerfile_base_name}.{image_type}", "w") as f:
                        log.info(
                            f"[bright_black]Rendering [bold]{new_directory / f'{containerfile_base_name}.{image_type}'}"
                        )
                        f.write(rendered)
                    continue
            else:
                rendered = tpl.render(image_version=version, **value_map, **render_kwargs)
                rel_path = tpl_rel_path.removesuffix(".jinja2")
                target_dir = Path(new_directory / rel_path).parent
                target_dir.mkdir(parents=True, exist_ok=True)
                with open(new_directory / rel_path, "w") as f:
                    log.info(f"[bright_black]Rendering [bold]{new_directory / rel_path}")
                    f.write(rendered)

    def new_version(
        self, version: str, mark_latest: bool = True, save: bool = True, value_map: Dict[str, str] = None
    ) -> None:
        """Render a new version, add the version to the manifest document, and regenerate target builds

        :param version: Version to render and add to the manifest
        :param mark_latest: Mark the new version as the latest build and remove the latest flag from other versions
        :param save: If true, writes the updated manifest back to the manifest.toml file
        :param value_map: Map of values to use in the template rendering
        """
        self.render_image_template(version, value_map)
        if version in self.document["build"]:
            log.warning(
                f"Build version '{version}' already exists in manifest '{self.filepath}'. Please update the manifest.toml manually if necessary."
            )
        else:
            self.append_build_version(version, mark_latest)
        self.target_builds = TargetBuild.load(self.config, self.context, self.document)
        if save:
            self.dump()
