import abc
import os
from pathlib import Path
from typing import Union

import tomlkit
from pydantic import BaseModel, ConfigDict


class GenericTOMLModel(BaseModel, abc.ABC):
    """Base class for TOML Document models

    :param filepath: Path to the TOML file represented by the model
    :param context: Path to the context (parent directory) of the TOML file
    :param document: tomlkit.TOMLDocument object
    """

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    filepath: Path
    context: Path
    document: tomlkit.TOMLDocument

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
        with open(filepath, "w") as f:
            tomlkit.dump(self.document, f)

    def dumps(self) -> str:
        """Return the TOMLDocument object as a string representation"""
        return tomlkit.dumps(self.document)
