import abc
import os
from pathlib import Path
from typing import Union

import tomlkit
from pydantic import BaseModel, ConfigDict


class GenericTOMLModel(BaseModel, abc.ABC):
    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
    filepath: Path
    context: Path
    document: tomlkit.TOMLDocument

    @staticmethod
    def load_toml_file_data(filepath: Union[str, bytes, os.PathLike]) -> tomlkit.TOMLDocument:
        with open(filepath, "rb") as f:
            return tomlkit.load(f)

    def dump(self, filepath: Union[str, bytes, os.PathLike] = None) -> None:
        if filepath is None:
            filepath = self.filepath
        filepath = Path(filepath)
        with open(filepath, "w") as f:
            tomlkit.dump(self.document, f)

    def dumps(self) -> str:
        return tomlkit.dumps(self.document)
