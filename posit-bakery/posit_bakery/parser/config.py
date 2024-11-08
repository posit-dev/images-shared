import os
from pathlib import Path
from typing import Optional, Set, Union

from pydantic.dataclasses import dataclass

from posit_bakery.parser.generic import GenericTOMLModel


@dataclass
class ConfigRegistry:
    host: str
    namespace: Optional[str]

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
    authors: Set[str]
    url: Optional[str]
    vendor: str = "Posit Software, PBC"
    maintainer: str = "docker@posit.co"


class Config(GenericTOMLModel):
    registry: Set[ConfigRegistry]
    repository: ConfigRepository

    @classmethod
    def load_file(cls, filepath: Union[str, bytes, os.PathLike]) -> "Config":
        filepath = Path(filepath)
        d = cls.__load_file_data(filepath)
        registry = []
        for r in d["registry"]:
            registry.append(ConfigRegistry(**r))
        repository = ConfigRepository(**d["repository"])
        return cls(
            filepath=filepath,
            context=filepath.parent,
            __document=d,
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
