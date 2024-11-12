import os
import re
from datetime import timezone, datetime

from pathlib import Path
from typing import Dict, Union, List, Any, Set, Optional

import jinja2
from pydantic import model_validator
from pydantic.dataclasses import dataclass
from pydantic_core import ArgsKwargs
from tomlkit import TOMLDocument
from tomlkit.items import Table

from posit_bakery.error import BakeryConfigError, BakeryFileNotFoundError
from posit_bakery.parser.config import Config
from posit_bakery.parser.generic import GenericTOMLModel
from posit_bakery.parser.templating.filters import render_template, condense, tag_safe, clean_version, jinja2_env


@dataclass
class GossConfig:
    version_context: Union[str, bytes, os.PathLike]
    build_data: Dict[str, Any]
    target_data: Dict[str, Any]
    const: Dict[str, Any] = None

    deps: Path = None
    test_path: Path = None
    wait: int = 0
    command: str = "sleep infinity"

    def __post_init__(self):
        if self.deps is None:
            self.deps = Path(self.version_context) / "deps"
        if self.test_path is None:
            self.test_path = Path(self.version_context) / "test"

        if self.deps:
            self.deps = Path(
                render_template(str(self.deps), build=self.build_data, target=self.target_data, **self.const)
            )
        if self.test_path:
            self.test_path = Path(
                render_template(str(self.test_path), build=self.build_data, target=self.target_data, **self.const)
            )
        if self.wait:
            self.wait = int(render_template(str(self.wait), build=self.build_data, target=self.target_data, **self.const))
        if self.command:
            self.command = render_template(self.command, build=self.build_data, target=self.target_data, **self.const)


@dataclass
class TargetBuild:
    manifest_context: Union[str, bytes, os.PathLike]
    config: Config
    build_data: Dict[str, Any]
    target_data: Dict[str, Any]

    image_name: str
    version: str
    type: str

    const: Dict[str, Any] = None
    os: Optional[str] = None
    containerfile: str = None
    containerfile_path: Path = None
    latest: bool = False
    primary_os: bool = False
    tags: List[str] = None
    latest_tags: List[str] = None
    goss: GossConfig = None

    @property
    def all_tags(self) -> List[str]:
        tags = []
        for base_url in self.config.registry_urls:
            for tag in self.tags:
                tags.append(f"{base_url}/{self.image_name}:{tag}")
            if self.latest:
                for tag in self.latest_tags:
                    tags.append(f"{base_url}/{self.image_name}:{tag}")
        return tags

    @property
    def uid(self):
        return re.sub("[.+/]", "-", f"{self.image_name}-{self.version}-{self.os}-{self.type}")

    @property
    def labels(self):
        labels = {
            "co.posit.image.name": self.image_name,
            "co.posit.image.os": self.os,
            "co.posit.image.type": self.type,
            "co.posit.image.version": self.version,
            "org.opencontainers.image.created": datetime.now(tz=timezone.utc).isoformat(),
            "org.opencontainers.image.title": self.image_name,
            "org.opencontainers.image.vendor": self.config.vendor,
            "org.opencontainers.image.maintainer": self.config.maintainer,
            "org.opencontainers.image.revision": self.config.get_commit_sha(),
        }
        if self.config.authors:
            labels["org.opencontainers.image.authors"] = ", ".join(self.config.authors)
        if self.config.repository_url:
            labels["org.opencontainers.image.source"] = self.config.repository_url
        return labels

    @model_validator(mode="before")
    @classmethod
    def pre_root(cls, values: ArgsKwargs) -> ArgsKwargs:
        if "goss" in values.kwargs:
            version_context = values.kwargs["manifest_context"] / values.kwargs["version"]
            const = values.kwargs.get("const")
            if const is None:
                const = {"image_name": values.kwargs["image_name"]}
            values.kwargs["goss"] = GossConfig(
                version_context=version_context,
                build_data=values.kwargs["build_data"],
                target_data=values.kwargs["target_data"],
                const=const,
                **values.kwargs["goss"]
            )
        return values

    def __post_init__(self):
        if self.const is None:
            self.const = {"image_name": self.image_name}
        if "image_name" not in self.const:
            self.const["image_name"] = self.image_name

        if self.os is None and "os" in self.const:
            self.os = self.const["os"]
        elif self.os is None:
            raise ValueError(f"No operating system could be determined for manifest '{self.uid}'.")

        if self.containerfile is None:
            condensed_os = condense(self.os)
            potential_names = [f"Containerfile.{condensed_os}.{self.type}", f"Containerfile.{self.type}", "Containerfile"]
            for name in potential_names:
                potential_path = Path(self.manifest_context) / self.version / name
                if potential_path.exists():
                    self.containerfile = name
                    self.containerfile_path = potential_path
                    break
        else:
            self.containerfile = render_template(
                self.containerfile, build=self.build_data, target=self.target_data, **self.const
            )
            self.containerfile_path = Path(self.manifest_context) / self.version / self.containerfile

        if self.tags is None or len(self.tags) == 0:
            if self.type == "std":
                self.tags = [
                    f"{tag_safe(self.version)}-{condense(self.os)}",
                    f"{clean_version(self.version)}-{condense(self.os)}",
                ]
                if self.primary_os or "os" in self.const:
                    self.tags.append(f"{tag_safe(self.version)}")
            else:
                self.tags = [
                    f"{tag_safe(self.version)}-{condense(self.os)}-{self.type}",
                    f"{clean_version(self.version)}-{condense(self.os)}-{self.type}",
                ]
                if self.primary_os or "os" in self.const:
                    self.tags.append(f"{tag_safe(self.version)}-{self.type}")
        else:
            self.tags = [render_template(tag, build=self.build_data, target=self.target_data, **self.const) for tag in self.tags]

        if self.latest_tags is None or len(self.latest_tags) == 0:
            if self.type == "std":
                self.latest_tags = [f"{condense(self.os)}", "latest"]
            else:
                self.latest_tags = [f"{condense(self.os)}-{self.type}", f"latest-{self.type}"]
        else:
            self.latest_tags = [render_template(tag, build=self.build_data, target=self.target_data, **self.const) for tag in self.latest_tags]

        if self.goss is None:
            self.goss = GossConfig(
                version_context=self.manifest_context / self.version,
                build_data=self.build_data,
                target_data=self.target_data,
                const=self.const
            )

    def __hash__(self):
        return hash(self.uid)


class Manifest(GenericTOMLModel):
    image_name: str
    manifest_context: Path
    config: Config
    target_builds: Set[TargetBuild] = None

    @property
    def types(self) -> Set[str]:
        return set(target_build.type for target_build in self.target_builds)

    @property
    def versions(self) -> Set[str]:
        return set(target_build.version for target_build in self.target_builds)

    @staticmethod
    def generate_target_builds(config: Config, manifest_context: Path, manifest_document: TOMLDocument):
        target_builds = []
        for build_version, build_data in manifest_document["build"].unwrap().items():
            os_list = build_data.pop("os", build_data.get("const", {}).pop("os", None))
            if os_list is None or type(os_list) is str:
                os_list = [os_list]
            for _os in os_list:
                for target_type, target_data in manifest_document["target"].unwrap().items():
                    target_builds.append(TargetBuild(
                        manifest_context=manifest_context,
                        config=config,
                        build_data=build_data,
                        target_data=target_data,
                        image_name=str(manifest_document["image_name"]),
                        version=build_version,
                        type=target_type,
                        os=_os,
                        const=manifest_document.get("const"),
                        **build_data,
                        **target_data,
                    ))
        return target_builds

    @classmethod
    def load_file_with_config(cls, config: Config, filepath: Union[str, bytes, os.PathLike]) -> "Manifest":
        filepath = Path(filepath)
        d = cls.load_toml_file_data(filepath)
        image_name = d.get("image_name")
        if image_name is None:
            raise BakeryConfigError(f"Manifest at '{filepath}' does not have an 'image_name' field.")
        target_builds = cls.generate_target_builds(config, Path(filepath).parent, d)
        return cls(
            filepath=filepath,
            document=d,
            context=config.context,
            image_name=image_name,
            manifest_context=Path(filepath).parent,
            config=config,
            target_builds=target_builds,
        )

    @staticmethod
    def __guess_os_list(p: Path):
        os_list = []
        pat = re.compile(r"Containerfile\.([a-zA-Z]+)([0-9.]+)\.[a-zA-Z0-9]")
        containerfiles = list(p.glob("Containerfile*"))
        containerfiles = [
            str(containerfile.relative_to(p)) for containerfile in containerfiles
        ]
        for containerfile in containerfiles:
            match = pat.match(containerfile)
            if match:
                os_list.append(" ".join(match.groups()).title())
        return os_list

    def __add_build_version_to_manifest(self, version: str, mark_latest: bool = True):
        build_data = {}
        if mark_latest:
            for build in self.document["build"].values():
                build.pop("latest")
            build_data["latest"] = True
        if "os" not in self.document["const"]:
            build_data["os"] = self.__guess_os_list(self.manifest_context / version)
        self.document["build"].append(version, build_data)
        self.generate_target_builds(self.config, self.manifest_context, self.document)
        self.dump()

    def __render_templates(self, version: str, value_map: Dict[str, str] = None):
        template_directory = self.manifest_context / "template"
        if not template_directory.exists():
            raise BakeryFileNotFoundError(f"Path '{self.manifest_context}/template' does not exist.")
        new_directory = self.manifest_context / version
        new_directory.mkdir(exist_ok=True)

        if value_map is None:
            value_map = {}
        if "rel_path" not in value_map:
            value_map["rel_path"] = new_directory.relative_to(self.config.context)

        e = jinja2_env(
            loader=jinja2.FileSystemLoader(template_directory), autoescape=True, undefined=jinja2.StrictUndefined
        )
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
                        print(f"[bright_black]Rendering [bold]{new_directory / f'{containerfile_base_name}.{image_type}'}")
                        f.write(rendered)
                    continue
            else:
                rendered = tpl.render(image_version=version, **value_map, **render_kwargs)
                rel_path = tpl_rel_path.removesuffix(".jinja2")
                target_dir = Path(new_directory / rel_path).parent
                target_dir.mkdir(parents=True, exist_ok=True)
                with open(new_directory / rel_path, "w") as f:
                    print(f"[bright_black]Rendering [bold]{new_directory / rel_path}")
                    f.write(rendered)

    def new_version(self, version: str, mark_latest: bool = True, value_map: Dict[str, str] = None):
        self.__render_templates(version, value_map)
        if version in self.document["build"]:
            raise BakeryConfigError(f"Version '{version}' already exists in manifest '{self.filepath}'.")
        self.__add_build_version_to_manifest(version, mark_latest)
