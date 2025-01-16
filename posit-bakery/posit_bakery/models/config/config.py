import logging
import os
from pathlib import Path
from typing import Set, Union, List

import git

from posit_bakery.models.generic import GenericTOMLModel
from posit_bakery.models.config.registry import ConfigRegistry
from posit_bakery.models.config.repository import ConfigRepository

log = logging.getLogger("rich")


class Config(GenericTOMLModel):
    """Models a repository's config.toml file

    :param __registries: One or more image registries to use for tagging and pushing images
    :param repository: Repository information for labeling purposes
    """

    __registries: List[ConfigRegistry]
    repository: ConfigRepository

    @property
    def registries(self) -> List[ConfigRegistry]:
        """Get the registries for the Config object"""
        r = list(self.__registries)
        r.sort(key=lambda x: x.base_url)
        return r

    @registries.setter
    def registries(self, r: List[ConfigRegistry]) -> None:
        """Set the registries for the Config object"""
        self.__registries = set(r)

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
        return [r.base_url for r in self.registries]

    def get_commit_sha(self) -> str:
        """Get the git commit SHA for the current context"""
        sha = ""
        try:
            repo = git.Repo(self.context)
            sha = repo.head.object.hexsha
        except Exception as e:
            log.error(f"Unable to get git commit for labels: {e}")
        return sha

    @classmethod
    def load(cls, filepath: Union[str, bytes, os.PathLike]) -> "Config":
        """Load a Config object from a TOML file

        :param filepath: Path to the config.toml file
        """
        filepath = Path(filepath)
        d = cls.read(filepath)

        # Create registry objects for each registry defined in config.toml
        registries = []
        for r in d["registries"]:
            registries.append(ConfigRegistry(**r))

        # Create repository object from config.toml
        repository = ConfigRepository(**d.get("repository", {}))

        return cls(filepath=filepath, context=filepath.parent, document=d, registries=registries, repository=repository)

    def update(self, c: "Config") -> None:
        """Replace data in the current Config object with data from another Config object

        This is used to overlay config.override.toml data on top of config.toml data when applicable

        :param c: Config object to overwrite onto the current object
        """
        # Only replace registries if defined in the provided config
        if len(c.registries) > 0:
            self.registries = c.registries

        # Only replace repository data if defined in the provided config
        if c.repository.authors:
            self.repository.authors = c.repository.authors
        if c.repository.url:
            self.repository.url = c.repository.url
        if c.repository.vendor:
            self.repository.vendor = c.repository.vendor
        if c.repository.maintainer:
            self.repository.maintainer = c.repository.maintainer
