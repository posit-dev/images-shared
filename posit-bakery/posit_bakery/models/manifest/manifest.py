import logging
import os

from pathlib import Path
from typing import Union, List

from posit_bakery.models.generic import GenericTOMLModel
from posit_bakery.models.manifest.document import ManifestDocument


log = logging.getLogger("rich")


class Manifest(GenericTOMLModel):
    """Simple wrapper around an image manifest.toml file"""

    @classmethod
    def load(cls, filepath: Union[str, bytes, os.PathLike]) -> "Manifest":
        """Load a Config object from a TOML file

        :param filepath: Path to the config.toml file
        """
        filepath = Path(filepath)
        document = cls.read(filepath)
        model = ManifestDocument(**document.unwrap())

        return cls(filepath=filepath, context=filepath.parent, document=document, model=model)

    @property
    def image_name(self) -> str:
        return str(self.model.image_name)

    @property
    def types(self) -> List[str]:
        """Get the target types present in the target builds"""
        return [_type for _type in self.model.target.keys()]

    @property
    def versions(self) -> List[str]:
        """Get the build versions present in the target builds"""
        return [version for version in self.model.build.keys()]
