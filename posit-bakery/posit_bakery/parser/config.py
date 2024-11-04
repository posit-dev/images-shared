import os
from pathlib import Path
from typing import Union, List, Dict, Optional

import tomlkit
from rich import print
from tomlkit import TOMLDocument
from tomlkit.items import AoT

from posit_bakery.error import BakeryConfigError


class Config:
    def __init__(
            self,
            config_file: Union[str, bytes, os.PathLike],
            override_config_file: Union[str, bytes, os.PathLike] = None,
    ) -> None:
        # The config.toml file for the project
        self.config_file: Path = Path(config_file)
        if not self.config_file.exists():
            print(
                f"[bright_red bold]ERROR:[/bold] No config file found at {self.config_file}. "
                f"A `config.toml` file is required in the context root."
            )
            raise BakeryConfigError(f"No config file found at {self.config_file}")

        # Load the config file data
        self.config_data: TOMLDocument = self.load(self.config_file)

        # The registries to push images to
        self.registries: Union[AoT, List[Dict[str, str]]] = self.config_data.get("registry", None)
        if not self.registries:
            raise BakeryConfigError("No registries found in config file")

        # The repository URL for the project, used for labeling purposes
        self.repository_url: Optional[str] = self.config_data["repository"].get("url", None)

        # The image vendor, used for labeling purposes
        self.vendor: str = self.config_data["repository"].get("vendor", "Posit Software, PBC")
        self.maintainer: str = self.config_data["repository"].get("maintainer", "docker@posit.co")
        self.authors: List[str] = self.config_data["repository"].get("authors", [])

        if override_config_file is not None:
            override_config_file = Path(override_config_file)
            if override_config_file.exists():
                self.override_config_file: Path = override_config_file
                self.override_config_data: TOMLDocument = self.load(self.override_config_file)
                if self.override_config_data.get("registry", None):
                    self.registries: Union[AoT, List[Dict[str, str]]] = self.override_config_data["registry"]
                if self.override_config_data.get("repository", None):
                    self.repository_url: str = self.override_config_data["repository"].get("url", self.repository_url)
                    self.vendor: str = self.override_config_data["repository"].get("vendor", self.vendor)
                    self.maintainer: str = self.override_config_data["repository"].get("maintainer", self.maintainer)
                    self.authors: List[str] = self.override_config_data["repository"].get("authors", self.authors)

    @staticmethod
    def load(config_file: Union[str, bytes, os.PathLike]) -> TOMLDocument:
        """Loads a TOML file into a TOMLDocument object

        :param config_file: The path to the TOML file
        """
        with open(config_file, "rb") as f:
            return tomlkit.load(f)

    def get_registry_base_urls(self) -> List[str]:
        """Returns a list of constructed registry base URLs"""
        return [f"{r['host']}/{r['namespace']}" for r in self.registries]

    @classmethod
    def load_config_from_context(cls, context: Union[str, bytes, os.PathLike], skip_override: bool = False) -> "Config":
        """Loads a Config object from a context directory

        :param context: The context directory
        :param skip_override: Skip loading the override config file
        """
        context = Path(context)
        config_file = context / "config.toml"
        if not config_file.exists():
            print(
                f"[bright_red bold]ERROR:[/bold] No config file found at {config_file}. "
                f"A `config.toml` file is required in the context root."
            )
            raise BakeryConfigError(f"No config file found at {config_file}")
        override_config_file = None
        if not skip_override:
            override_config_file = context / "config.override.toml"
        return cls(config_file, override_config_file)
