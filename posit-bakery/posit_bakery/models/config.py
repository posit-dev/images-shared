import os
from pathlib import Path
from typing import Optional, Set, Union

import git
from pydantic.dataclasses import dataclass
from rich import print

from posit_bakery.models.generic import GenericTOMLModel


@dataclass
class ConfigRegistry:
    host: str
    namespace: Optional[str] = None

    @property
    def base_url(self) -> str:
        u: str = f"{self.host}"
        if self.namespace:
            u = f"{u}/{self.namespace}"
        return u

    def __hash__(self):
        return hash(self.base_url + self.namespace)


@dataclass
class ConfigRepository:
    authors: Set[str] = None
    url: Optional[str] = None
    vendor: Optional[str] = "Posit Software, PBC"
    maintainer: Optional[str] = "docker@posit.co"


class Config(GenericTOMLModel):
    registry: Set[ConfigRegistry]
    repository: ConfigRepository

    @property
    def authors(self):
        return self.repository.authors

    @property
    def repository_url(self):
        return self.repository.url

    @property
    def vendor(self):
        return self.repository.vendor

    @property
    def maintainer(self):
        return self.repository.maintainer

    @property
    def registry_urls(self):
        return [r.base_url for r in self.registry]

    def get_commit_sha(self) -> str:
        """Get the git commit SHA for the current context"""
        sha = ""
        try:
            repo = git.Repo(self.context)
            sha = repo.head.object.hexsha
        except Exception as e:
            print(f"[bright_red][bold]ERROR:[/bold] Unable to get git commit for labels: {e}")
        return sha

    @classmethod
    def load_file(cls, filepath: Union[str, bytes, os.PathLike]) -> "Config":
        filepath = Path(filepath)
        d = cls.load_toml_file_data(filepath)
        registry = []
        for r in d["registry"]:
            registry.append(ConfigRegistry(**r))
        repository = ConfigRepository(**d["repository"])
        return cls(
            filepath=filepath,
            context=filepath.parent,
            document=d,
            registry=registry,
            repository=repository
        )

    def merge(self, c: "Config"):
        if len(c.registry) > 0:
            self.registry = c.registry
        if c.repository.authors:
            self.repository.authors = c.repository.authors
        if c.repository.url:
            self.repository.url = c.repository.url
        if c.repository.vendor:
            self.repository.vendor = c.repository.vendor
        if c.repository.maintainer:
            self.repository.maintainer = c.repository.maintainer
