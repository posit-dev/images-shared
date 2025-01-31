import logging
import os
from pathlib import Path
from typing import Set, Union, List

import git

from posit_bakery.models.generic import GenericTOMLModel
from posit_bakery.models.config.document import ConfigDocument
from posit_bakery.models.config.registry import ConfigRegistry
from posit_bakery.models.config.repository import ConfigRepository

log = logging.getLogger("rich")


def get_commit_sha(context: Path) -> str | None:
    """Get the git commit SHA for the current context"""
    sha = None
    try:
        repo = git.Repo(context, search_parent_directories=True)
        sha = repo.head.object.hexsha
    except Exception as e:
        log.debug(f"Unable to get git commit for labels: {e}")
    return sha


class Config(GenericTOMLModel):
    """Simple wrapper around a project config.toml file"""

    commit: str | None = None

    @classmethod
    def load(cls, filepath: Union[str, bytes, os.PathLike]) -> "Config":
        """Load a Config object from a TOML file

        :param filepath: Path to the config.toml file
        """
        filepath = Path(filepath)
        document = cls.read(filepath)
        model = ConfigDocument(**document.unwrap())
        commit = get_commit_sha(filepath.parent)

        return cls(filepath=filepath, context=filepath.parent, document=document, model=model, commit=commit)

    @property
    def registries(self) -> List[ConfigRegistry]:
        """Get the registries for the Config object"""
        return self.model.registries

    @property
    def authors(self) -> Set[str]:
        """Get the authors for the ConfigRepository object"""
        return self.model.repository.authors

    @property
    def repository_url(self) -> str:
        """Get the repository URL for the ConfigRepository object"""
        return self.model.repository.url

    @property
    def vendor(self) -> str:
        """Get the vendor for the ConfigRepository object"""
        return self.model.repository.vendor

    @property
    def maintainer(self) -> str:
        """Get the maintainer for the ConfigRepository object"""
        return self.model.repository.maintainer

    @property
    def registry_urls(self) -> List[str]:
        """Get the base URLs for all the ConfigRegistry objects as a list"""
        return [r.base_url for r in self.registries]

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
