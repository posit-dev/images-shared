import abc
import logging
import os
from pathlib import Path
from typing import Union, Mapping
from xml.dom.minidom import Comment

import tomlkit
from pydantic import BaseModel, ConfigDict
from ruamel.yaml import YAML, CommentedMap


class GenericYAMLModel(BaseModel, abc.ABC):
    """Base class for YAML Document models

    :param filepath: Path to the YAML file represented by the model
    :param context: Path to the context (parent directory) of the YAML file
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    filepath: Path
    context: Path
    document: CommentedMap | dict
    model: BaseModel | None = None

    @staticmethod
    def read(filepath: Union[str, bytes, os.PathLike]) -> CommentedMap | dict:
        """Load a YAML file at the given filepath into a TOMLDocument object

        :param filepath: Path to the YAML file
        """
        y = YAML()
        return y.load(Path(filepath))

    def dump(self, filepath: Union[str, bytes, os.PathLike] = None) -> None:
        """Write the YAML document to a file

        :param filepath: Path to write the YAML file to (defaults to self.filepath)
        """
        if filepath is None:
            filepath = self.filepath
        filepath = Path(filepath)
        logging.debug(f"Writing YAML document to {filepath}")
        y = YAML()
        y.dump(self.document, Path(filepath))


class GenericTOMLModel(BaseModel, abc.ABC):
    """Base class for TOML Document models

    :param filepath: Path to the TOML file represented by the model
    :param context: Path to the context (parent directory) of the TOML file
    :param document: tomlkit.TOMLDocument object
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    filepath: Path
    context: Path
    document: tomlkit.TOMLDocument
    model: BaseModel | None = None

    @staticmethod
    def read(filepath: Union[str, bytes, os.PathLike]) -> tomlkit.TOMLDocument:
        """Load a TOML file at the given filepath into a TOMLDocument object

        :param filepath: Path to the TOML file
        """
        with open(filepath, "rb") as f:
            return tomlkit.load(f)

    def dump(self, filepath: Union[str, bytes, os.PathLike] = None) -> None:
        """Write the TOMLDocument object to a file

        :param filepath: Path to write the TOML file to (defaults to self.filepath)
        """
        if filepath is None:
            filepath = self.filepath
        filepath = Path(filepath)
        logging.debug(f"Writing TOMLDocument to {filepath}")
        with open(filepath, "w") as f:
            tomlkit.dump(self.document, f)

    def dumps(self) -> str:
        """Return the TOMLDocument object as a string representation"""
        return tomlkit.dumps(self.document)
