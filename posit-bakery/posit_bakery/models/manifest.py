import os
import re
from datetime import timezone, datetime

from pathlib import Path
from typing import Dict, Union, List, Any, Set, Optional

import jinja2
from pydantic import model_validator, BaseModel
from pydantic.dataclasses import dataclass
from pydantic_core import ArgsKwargs
from rich import print
from tomlkit import TOMLDocument

from posit_bakery.error import BakeryConfigError, BakeryFileNotFoundError
from posit_bakery.models.config import Config
from posit_bakery.models.generic import GenericTOMLModel
from posit_bakery.templating.filters import render_template, condense, tag_safe, clean_version, jinja2_env


@dataclass
class GossConfig:
    version_context: Union[str, bytes, os.PathLike]
    build_data: Dict[str, Any]
    target_data: Dict[str, Any]
    const: Dict[str, Any]

    deps: Path = None
    test_path: Path = None
    wait: int = 0
    command: str = "sleep infinity"

    @model_validator(mode="before")
    @classmethod
    def pre_root(cls, values: ArgsKwargs) -> ArgsKwargs:
        # If the wait value is a string, render it
        if "wait" in values.kwargs and type(values.kwargs["wait"]) is str:
            values.kwargs["wait"] = int(
                render_template(
                    str(values.kwargs["wait"]),
                    build=values.kwargs["build_data"],
                    target=values.kwargs["target_data"],
                    **values.kwargs["const"],
                )
            )
        return values

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
        if self.command:
            self.command = render_template(self.command, build=self.build_data, target=self.target_data, **self.const)


class TargetBuild(BaseModel):
    manifest_context: Union[str, bytes, os.PathLike]
    config: Config
    build_data: Dict[str, Any]
    target_data: Dict[str, Any]

    image_name: str
    version: str
    type: str
    build_os: str

    const: Optional[Dict[str, Any]] = None
    containerfile_path: Path = None
    latest: bool = False
    primary_os: bool = False
    generic_tags: List[str] = None
    latest_tags: List[str] = None

    goss: GossConfig = None

    @property
    def uid(self):
        return re.sub("[.+/]", "-", f"{self.image_name}-{self.version}-{condense(self.build_os)}-{self.type}")

    @property
    def labels(self):
        labels = {
            "co.posit.image.name": self.image_name,
            "co.posit.image.os": self.build_os,
            "co.posit.image.type": self.type,
            "co.posit.image.version": self.version,
            "org.opencontainers.image.created": datetime.now(tz=timezone.utc).isoformat(),
            "org.opencontainers.image.title": self.image_name,
            "org.opencontainers.image.vendor": self.config.vendor,
            "org.opencontainers.image.maintainer": self.config.maintainer,
            "org.opencontainers.image.revision": self.config.get_commit_sha(),
        }
        if self.config.authors:
            authors = list(self.config.authors)
            authors.sort()
            labels["org.opencontainers.image.authors"] = ", ".join(authors)
        if self.config.repository_url:
            labels["org.opencontainers.image.source"] = self.config.repository_url
        return labels

    @model_validator(mode="before")
    @classmethod
    def unpack_goss(cls, data: Any) -> Any:
        if isinstance(data, dict) and "goss" in data:
            version_context = Path(data["manifest_context"]) / data["version"]
            const = data.get("const")
            if const is None:
                const = {"image_name": data["image_name"]}
            data["goss"] = GossConfig(
                version_context=version_context,
                build_data=data["build_data"],
                target_data=data["target_data"],
                const=const,
                **data["goss"],
            )
        return data

    @model_validator(mode="before")
    @classmethod
    def resolve_containerfile(cls, data: Any) -> Any:
        if isinstance(data, dict) and "containerfile" in data:
            version_context = Path(data["manifest_context"]) / data["version"]
            const = data.get("const")
            if const is None:
                const = {"image_name": data["image_name"]}
            data["containerfile_path"] = version_context / render_template(
                data.pop("containerfile"),
                build=data["build_data"],
                target=data["target_data"],
                **const,
            )
        return data

    @model_validator(mode="before")
    @classmethod
    def set_build_os(cls, data: Any) -> Any:
        if isinstance(data, dict) and "os" in data and "build_os" not in data:
            data["build_os"] = data.pop("os")
        return data

    def model_post_init(self, __context: Any) -> None:
        self.manifest_context = Path(self.manifest_context)
        if not self.manifest_context.is_dir():
            raise BakeryFileNotFoundError(f"Manifest context '{self.manifest_context}' is not a directory.")

        if self.const is None:
            self.const = {"image_name": self.image_name}
        if "image_name" not in self.const:
            self.const["image_name"] = self.image_name

        if self.build_os is None:
            raise ValueError(f"No operating system could be determined for manifest '{self.uid}'.")

        if self.containerfile_path is None:
            self.containerfile_path = self.__find_containerfile(
                self.manifest_context / self.version, self.type, self.build_os
            )
        if self.containerfile_path is None:
            raise BakeryFileNotFoundError(
                f"Could not find a Containerfile for manifest '{self.uid}' in '{self.manifest_context / self.version}'."
            )

        # Generate the generic tags if not provided, otherwise render them
        if self.generic_tags is None or len(self.generic_tags) == 0:
            self.generic_tags = [
                f"{tag_safe(self.version)}-{condense(self.build_os)}",
                f"{clean_version(self.version)}-{condense(self.build_os)}",
            ]
            if self.primary_os or "os" in self.const:
                self.generic_tags.extend([f"{tag_safe(self.version)}", f"{clean_version(self.version)}"])
            if self.type != "std":
                for i in range(len(self.generic_tags)):
                    self.generic_tags[i] = f"{self.generic_tags[i]}-{self.type}"
        else:
            self.generic_tags = [
                render_template(tag, build=self.build_data, target=self.target_data, **self.const)
                for tag in self.generic_tags
            ]

        # Generate the latest tags if not provided, otherwise render them
        if self.latest_tags is None or len(self.latest_tags) == 0:
            self.latest_tags = [f"{condense(self.build_os)}", "latest"]
            if self.type != "std":
                for i in range(len(self.latest_tags)):
                    self.latest_tags[i] = f"{self.latest_tags[i]}-{self.type}"
        else:
            self.latest_tags = [
                render_template(tag, build=self.build_data, target=self.target_data, **self.const)
                for tag in self.latest_tags
            ]

        if self.goss is None:
            self.goss = GossConfig(
                version_context=self.manifest_context / self.version,
                build_data=self.build_data,
                target_data=self.target_data,
                const=self.const,
            )

    @classmethod
    def load(cls, config: Config, manifest_context: Path, manifest_document: TOMLDocument) -> List["TargetBuild"]:
        """Generate a set of TargetBuild objects from a manifest document

        :param config: Config object for the repository
        :param manifest_context: Path to the directory containing the manifest and associated image definitions
        :param manifest_document: TOMLDocument object representing the manifest.toml file
        """
        target_builds = []

        # If the manifest document does not have at least one build and one target section, return an empty list.
        if "build" not in manifest_document:
            print(
                f"[bright_yellow][bold]WARNING:[/bold] Manifest '{manifest_context / 'manifest.toml'}' "
                f"does not have any defined builds."
            )
            return target_builds
        if "target" not in manifest_document:
            print(
                f"[bright_yellow][bold]WARNING:[/bold] Manifest '{manifest_context / 'manifest.toml'}' "
                f"does not have any defined targets."
            )
            return target_builds

        for build_version, build_data in manifest_document["build"].unwrap().items():
            os_list = build_data.pop("os", build_data.get("const", {}).pop("os", None))
            build_data["version"] = build_version
            if os_list is None or type(os_list) is str:
                os_list = [os_list]
            primary_os = os_list[0]
            for _os in os_list:
                for target_type, target_data in manifest_document["target"].unwrap().items():
                    target_data["type"] = target_type
                    target_builds.append(
                        cls(
                            manifest_context=manifest_context,
                            config=config,
                            build_data=build_data,
                            target_data=target_data,
                            image_name=str(manifest_document["image_name"]),
                            build_os=_os,
                            primary_os=_os == primary_os,
                            const=manifest_document.get("const"),
                            **build_data,
                            **target_data,
                        )
                    )
        return target_builds

    def get_tags(self, fully_qualified: bool = True) -> List[str]:
        tags = []
        for base_url in self.config.registry_urls:
            for tag in self.generic_tags:
                t = f"{self.image_name}:{tag}"
                if fully_qualified:
                    t = f"{base_url}/{t}"
                if t not in tags:
                    tags.append(t)
            if self.latest:
                for tag in self.latest_tags:
                    t = f"{self.image_name}:{tag}"
                    if fully_qualified:
                        t = f"{base_url}/{t}"
                    if t not in tags:
                        tags.append(t)
        tags.sort()
        return tags

    @staticmethod
    def __find_containerfile(
        search_context: Union[str, bytes, os.PathLike], image_type: str, build_os: str
    ) -> Path | None:
        condensed_os = condense(build_os)
        potential_names = [
            f"Containerfile.{condensed_os}.{image_type}",
            f"Containerfile.{image_type}",
            f"Containerfile.{condensed_os}",
            "Containerfile",
        ]
        for name in potential_names:
            potential_path = Path(search_context) / name
            if potential_path.is_file():
                return potential_path
        return None

    def __hash__(self):
        return hash(self.uid)


class Manifest(GenericTOMLModel):
    """Models an image's manifest.toml file

    :param image_name: Name of the image
    :param config: Config object for the repository
    :param target_builds: Set of TargetBuild objects for the image
    """

    image_name: str
    config: Config

    __target_builds: Set[TargetBuild] = None

    @property
    def types(self) -> Set[str]:
        """Get the target types present in the target builds"""
        return set(target_build.type for target_build in self.target_builds)

    @property
    def versions(self) -> Set[str]:
        """Get the build versions present in the target builds"""
        return set(target_build.version for target_build in self.target_builds)

    @property
    def target_builds(self) -> List[TargetBuild]:
        """Get the target builds for the manifest with consistent ordering"""
        if self.__target_builds is None:
            return []
        t = list(self.__target_builds)
        t.sort(key=lambda x: (x.version, x.type, x.build_os))
        return t

    @target_builds.setter
    def target_builds(self, value: List[TargetBuild]):
        """Set the target builds for the manifest"""
        t = set(value)
        self.__target_builds = t

    def filter_target_builds(
        self, build_version: str = None, target_type: str = None, build_os: str = None, is_latest: bool = None
    ) -> List[TargetBuild]:
        """Filter the target builds based on the given criteria

        :param build_version: Build version to filter by
        :param target_type: Target type to filter by
        :param build_os: Build OS to filter by
        :param is_latest: Filter latest build(s)
        """
        results = []
        for target_build in self.target_builds:
            if build_version is not None and target_build.version != build_version:
                continue
            if target_type is not None and target_build.type != target_type:
                continue
            if build_os is not None and target_build.build_os != build_os:
                continue
            if is_latest is not None and target_build.latest != is_latest:
                continue
            results.append(target_build)
        return results

    @classmethod
    def load(cls, config: Config, filepath: Union[str, bytes, os.PathLike]) -> "Manifest":
        """Load a Manifest object from a TOML file

        :param config: Config object for the repository
        :param filepath: Path to the manifest.toml file to load
        """
        filepath = Path(filepath)
        d = cls.read(filepath)
        image_name = d.get("image_name")
        if image_name is None:
            raise BakeryConfigError(f"Manifest at '{filepath}' does not have an 'image_name' field.")
        target_builds = TargetBuild.load(config, Path(filepath).parent, d)
        m = cls(
            filepath=filepath,
            document=d,
            context=Path(filepath).parent,
            image_name=image_name,
            config=config,
        )
        m.target_builds = target_builds
        return m

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

    def append_build_version(self, version: str, mark_latest: bool = True) -> None:
        """Append a new build version to the manifest document

        :param version: Build version to append
        :param mark_latest: Mark the new build version as the latest and remove the latest flag from other versions
        """
        build_data = {}
        if mark_latest:
            for build in self.document["build"].values():
                build.pop("latest")
            build_data["latest"] = True
        if "os" not in self.document.get("const", {}):
            build_data["os"] = self.guess_image_os_list(self.context / version)
        self.document["build"].append(version, build_data)

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
                        print(
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
                    print(f"[bright_black]Rendering [bold]{new_directory / rel_path}")
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
            print(
                f"[bright_yellow][bold]WARNING:[/bold] Build version '{version}' already exists in "
                f"manifest '{self.filepath}'. Please update the manifest.toml manually if necessary."
            )
        else:
            self.append_build_version(version, mark_latest)
        self.target_builds = TargetBuild.load(self.config, self.context, self.document)
        if save:
            self.dump()
