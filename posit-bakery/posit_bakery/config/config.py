import os
from pathlib import Path

from pydantic import Field
from typing import Annotated

from pydantic import BaseModel
from ruamel.yaml import YAML

from posit_bakery.config.registry import Registry
from posit_bakery.config.repository import Repository
from posit_bakery.models import Image


class BakeryConfig:
    def __init__(self, config_file: str | Path | os.PathLike):
        self.yaml = YAML()
        self.config_file = Path(config_file)
        self.base_path = self.config_file.parent
        self.config = BakeryConfigDocument(base_path=self.base_path, **self.yaml.load(self.config_file))


class BakeryConfigDocument(BaseModel):
    base_path: Annotated[Path, Field(exclude=True)]
    repository: Repository
    registries: Annotated[list[Registry], Field(default_factory=list)]
    images: Annotated[list[Image], Field(default_factory=list)]
