import os
from pathlib import Path

from pydantic import Field, model_validator, computed_field
from typing import Annotated, Self
from ruamel.yaml import YAML

from posit_bakery.config.registry import Registry
from posit_bakery.config.repository import Repository
from posit_bakery.config.shared import BakeryBaseModel
from posit_bakery.config.image import Image


class BakeryConfigDocument(BakeryBaseModel):
    base_path: Annotated[Path, Field(exclude=True)]
    repository: Repository
    registries: Annotated[list[Registry], Field(default_factory=list)]
    images: Annotated[list[Image], Field(default_factory=list)]

    @model_validator(mode="after")
    def resolve_parentage(self) -> Self:
        for image in self.images:
            image.parent = self
        return self

    @computed_field
    @property
    def path(self) -> Path:
        """Returns the path to the bakery config directory."""
        return self.base_path


class BakeryConfig:
    def __init__(self, config_file: str | Path | os.PathLike):
        self.yaml = YAML()
        self.config_file = Path(config_file)
        self.base_path = self.config_file.parent
        self.config = BakeryConfigDocument(base_path=self.base_path, **self.yaml.load(self.config_file))

    @classmethod
    def from_cwd(cls, working_directory: str | Path | os.PathLike = os.getcwd()) -> "BakeryConfig":
        """Load the bakery config from the current working directory."""
        paths = [Path(working_directory) / "bakery.yaml", Path(working_directory) / "bakery.yml"]
        for path in paths:
            if path.exists():
                return cls(path)
        raise FileNotFoundError(f"No bakery.yaml config file found in {working_directory}.")
