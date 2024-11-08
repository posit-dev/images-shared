import os
from pathlib import Path
from typing import Union, List

from posit_bakery.error import BakeryFileNotFoundError
from posit_bakery.parser.config import Config
from posit_bakery.parser.manifest import Manifest


def load_context_config(context: Union[str, bytes, os.PathLike]) -> Config:
    context = Path(context)
    if not context.exists():
        raise BakeryFileNotFoundError(f"Directory {context} does not exist.")
    config_filepath = context / "config.toml"
    if not config_filepath.exists():
        raise BakeryFileNotFoundError(f"Config file {config_filepath} does not exist.")
    config = Config.load_file(config_filepath)

    override_config_filepath = context / "config.override.toml"
    if override_config_filepath.exists():
        override_config = Config.load_file(override_config_filepath)
        config.merge(override_config)

    return config


def load_config_manifests(config: Config) -> List["Manifest"]:
    """Loads all manifests from a context directory

    :param config: The project configuration
    """
    manifests = []
    for manifest_file in config.context.rglob("manifest.toml"):
        manifests.append(Manifest.load_file_with_config(config, manifest_file))
    return manifests


def load_context(context: Union[str, bytes, os.PathLike]) -> (Config, List[Manifest]):
    config = load_context_config(context)
    manifests = load_config_manifests(config)
    return config, manifests
