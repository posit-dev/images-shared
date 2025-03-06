import logging
import os

from pathlib import Path
from typing import Union, List

from posit_bakery.models.generic import GenericTOMLModel
from posit_bakery.models.manifest.document import ManifestDocument


log = logging.getLogger(__name__)


class Manifest(GenericTOMLModel):
    """Simple wrapper around an image manifest.toml file"""

    @classmethod
    def load(cls, filepath: Union[str, bytes, os.PathLike]) -> "Manifest":
        """Load a Config object from a TOML file

        :param filepath: Path to the config.toml file
        """
        log.debug(f"Loading Manifest from {filepath}")
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

    def add_version(self, version: str, os_list: List[str], latest: bool):
        existing_builds = self.document.get("build", {})
        log.debug(f"Adding version {version} to manifest {self.filepath}")

        if latest:
            for b in existing_builds.values():
                b.pop("latest", None)
            new_build = {"os": os_list, "latest": True}
        else:
            new_build = {"os": os_list}

        # TODO: Should we sort the manifest by version in descending order?
        builds = {**existing_builds, version: new_build}
        # Sort versions in descending order
        versions = builds.keys()
        builds = {str(v): builds[str(v)] for v in sorted(versions, reverse=True)}
        self.document["build"] = builds
        self.dump()
