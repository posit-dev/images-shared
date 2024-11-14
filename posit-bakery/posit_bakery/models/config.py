import os
from pathlib import Path
from typing import Optional, Set, Union, List

import git
from pydantic.dataclasses import dataclass
from rich import print

from posit_bakery.models.generic import GenericTOMLModel


@dataclass
class ConfigRegistry:
    """Configuration for a container image registry

    Used for tagging of images and pushing to the registry
    """
    host: str
    namespace: Optional[str] = None

    @property
    def base_url(self) -> str:
        """Get the base URL for the registry"""
        u: str = f"{self.host}"
        if self.namespace:
            u = f"{u}/{self.namespace}"
        return u

    def __hash__(self) -> int:
        """Unique hash for a ConfigRegistry object"""
        return hash(self.base_url + self.namespace)


@dataclass
class ConfigRepository:
    """Configuration for a container image repository

    Primarily used for labeling purposes

    :param authors: Authors of the repository images
    :param url: URL to the repository (e.g. github.com/rstudio/example)
    :param vendor: Vendor of the images in the repository
    :param maintainer: Maintainer of the images in the repository
    """
    authors: Set[str] = None
    url: Optional[str] = None
    vendor: Optional[str] = "Posit Software, PBC"
    maintainer: Optional[str] = "docker@posit.co"

    def __post_init__(self) -> None:
        # Initialize authors as an empty set if not provided
        if self.authors is None:
            self.authors = set()


class Config(GenericTOMLModel):
    """Models a repository's config.toml file

    :param registry: One or more image registries to use for tagging and pushing images
    :param repository: Repository information for labeling purposes
    """
    registry: Set[ConfigRegistry]
    repository: ConfigRepository

    @property
    def authors(self) -> Set[str]:
        """Get the authors for the ConfigRepository object"""
        return self.repository.authors

    @property
    def repository_url(self) -> str:
        """Get the repository URL for the ConfigRepository object"""
        return self.repository.url

    @property
    def vendor(self) -> str:
        """Get the vendor for the ConfigRepository object"""
        return self.repository.vendor

    @property
    def maintainer(self) -> str:
        """Get the maintainer for the ConfigRepository object"""
        return self.repository.maintainer

    @property
    def registry_urls(self) -> List[str]:
        """Get the base URLs for all the ConfigRegistry objects as a list"""
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
        """Load a Config object from a TOML file

        :param filepath: Path to the config.toml file
        """
        filepath = Path(filepath)
        d = cls.load_toml_file_data(filepath)

        # Create registry objects for each registry defined in config.toml
        registry = []
        for r in d["registry"]:
            registry.append(ConfigRegistry(**r))

        # Create repository object from config.toml
        repository = ConfigRepository(**d["repository"])

        return cls(
            filepath=filepath,
            context=filepath.parent,
            document=d,
            registry=registry,
            repository=repository
        )

    def merge(self, c: "Config") -> None:
        """Replace data in the current Config object with data from another Config object

        This is used to overlay config.override.toml data on top of config.toml data when applicable

        :param c: Config object to overwrite onto the current object
        """
        # Only replace registries if defined in the provided config
        if len(c.registry) > 0:
            self.registry = c.registry

        # Only replace repository data if defined in the provided config
        if c.repository.authors:
            self.repository.authors = c.repository.authors
        if c.repository.url:
            self.repository.url = c.repository.url
        if c.repository.vendor:
            self.repository.vendor = c.repository.vendor
        if c.repository.maintainer:
            self.repository.maintainer = c.repository.maintainer
