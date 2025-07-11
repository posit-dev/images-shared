from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field

from posit_bakery.config.registry import Registry
from posit_bakery.config.tag import TagPattern
from posit_bakery.config.tools import default_tool_options
from posit_bakery.config.tools.base import ToolOptions


class ImageVersionOS(BaseModel):
    name: str
    extension: Annotated[str | None, Field(default=None, pattern=r"^[a-zA-Z0-9_-]+$")]
    tagDisplayName: Annotated[str | None, Field(default=None, pattern=r"^[a-zA-Z0-9_-.]+$")]
    primary: Annotated[bool, Field(default=False)]


class ImageVersion(BaseModel):
    name: str
    subpath: str | None
    registries: list[Registry]
    latest: Annotated[bool, Field(default=False)]
    os: list[str | ImageVersionOS]


class ImageVariant(BaseModel):
    name: str
    tags: list[str | TagPattern]
    options: Annotated[list[ToolOptions], Field(default_factory=default_tool_options)]


class Image(BaseModel):
    name: str
    subpath: str | None
    registries: list[Registry]
    tags: list[str | TagPattern]
    variants: list[ImageVariant]
