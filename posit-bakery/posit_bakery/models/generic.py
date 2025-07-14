import abc
import logging
import os
from pathlib import Path
from typing import Union

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
        """Load a YAML file at the given filepath into a CommentedMap or dict

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
