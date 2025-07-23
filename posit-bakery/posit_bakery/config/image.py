from typing import Annotated

from pydantic import BaseModel, Field

from posit_bakery.config.registry import Registry
from posit_bakery.config.tag import TagPattern
from posit_bakery.config.tools import ToolTypes, ToolField


class ImageVersionOS(BaseModel):
    parent: Annotated[BaseModel, Field(exclude=True)]
    name: str
    extension: Annotated[str | None, Field(default=None, pattern=r"^[a-zA-Z0-9_-]+$")]
    tagDisplayName: Annotated[str | None, Field(default=None, pattern=r"^[a-zA-Z0-9_-.]+$")]
    primary: Annotated[bool, Field(default=False)]


class ImageVersion(BaseModel):
    parent: Annotated[BaseModel, Field(exclude=True)]
    name: str
    subpath: str | None
    registries: list[Registry]
    latest: Annotated[bool, Field(default=False)]
    os: list[str | ImageVersionOS]


class ImageVariant(BaseModel):
    parent: Annotated[BaseModel, Field(exclude=True)]
    name: str
    tags: list[str | TagPattern]
    options: Annotated[ToolTypes, ToolField()]


class Image(BaseModel):
    parent: Annotated[BaseModel, Field(exclude=True)]
    name: str
    subpath: str | None
    registries: list[Registry]
    tags: list[str | TagPattern]
    variants: list[ImageVariant]
