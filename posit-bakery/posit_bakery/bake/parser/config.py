import tomllib
from pathlib import Path

from rich import print

from posit_bakery.error import BakeryConfigError


class Config:
    def __init__(self, config_file: Path, override_config_file: Path = None):
        self.config_file = config_file
        self.config_data = self.load(self.config_file)
        self.registries = self.config_data.get("registry", None)
        if not self.registries:
            raise BakeryConfigError("No registries found in config file")
        self.repository_url = self.config_data["repository"].get("url", None)
        self.vendor = self.config_data["repository"].get("vendor", "Posit Software, PBC")
        self.maintainer = self.config_data["repository"].get("maintainer", "docker@posit.co")
        self.authors = self.config_data["repository"].get("authors", [])

        if override_config_file and override_config_file.exists():
            self.override_config_file = override_config_file
            self.override_config_data = self.load(self.override_config_file)
            if self.override_config_data.get("registry", None):
                self.registries = self.override_config_data["registry"]
            if self.override_config_data.get("repository", None):
                self.repository_url = self.override_config_data["repository"].get("url", self.repository_url)
                self.vendor = self.override_config_data["repository"].get("vendor", self.vendor)
                self.maintainer = self.override_config_data["repository"].get("maintainer", self.maintainer)
                self.authors = self.override_config_data["repository"].get("authors", self.authors)

    @staticmethod
    def load(config_file: Path):
        with open(config_file, "rb") as f:
            return tomllib.load(f)

    def get_registry_base_urls(self):
        return [f"{r['host']}/{r['namespace']}" for r in self.registries]

    @classmethod
    def load_config_from_context(cls, context: Path):
        config_file = context / "config.toml"
        if not config_file.exists():
            print(
                f"[bright_red bold]ERROR:[/bold] No config file found at {config_file}. "
                f"A `config.toml` file is required in the context root."
            )
            raise BakeryConfigError(f"No config file found at {config_file}")
        override_config_file = context / "config.override.toml"
        return cls(config_file, override_config_file)
