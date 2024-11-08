import os
import re

from pathlib import Path
from typing import Dict, Union, List, Any, Set

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

    uid: str = None
    const: Dict[str, Any] = None
    os: str = None
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
        for registry in self.config.registry:
            for tag in self.tags:
                tags.append(f"{registry.base_url}/{self.image_name}:{tag}")
            if self.latest:
                for tag in self.latest_tags:
                    tags.append(f"{registry.base_url}/{self.image_name}:{tag}")
        return tags

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
        if self.uid is None:
            self.uid = re.sub("[.+/]", "-", f"{self.image_name}-{self.version}-{self.type}")

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
                        image_name=manifest_document["image_name"],
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
        d = cls.__load_file_data(filepath)
        image_name = d.get("image_name")
        if image_name is None:
            raise BakeryConfigError(f"Manifest at '{filepath}' does not have an 'image_name' field.")
        target_builds = cls.generate_target_builds(config, Path(filepath).parent, d)
        return cls(
            filepath=filepath,
            __document=d,
            context=config.context,
            image_name=image_name,
            manifest_context=Path(filepath).parent,
            config=config,
            target_builds=target_builds,
        )

        :param context: The context directory
        :param image_name: Filter the manifests loaded by image name
        :param image_version: Filter the manifests loaded by image version
        """
        manifests = {}
        context = Path(context)
        for manifest_file in context.rglob("manifest.toml"):
            manifest_name = str(manifest_file.parent.relative_to(context))
            if image_name and image_name != manifest_name:
                continue
            manifests[manifest_name] = cls(
                context, manifest_name, manifest_file, {"image_version": image_version}
            )
        return manifests
