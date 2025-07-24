from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator

from posit_bakery.config.registry import Registry
from posit_bakery.config.tag import TagPattern, default_tag_patterns
from posit_bakery.config.tools import ToolTypes, ToolField, default_tool_options, ToolOptions


class ImageVersionOS(BaseModel):
    parent: Annotated[BaseModel | None, Field(exclude=True, default=None)]
    name: str
    extension: Annotated[str | None, Field(default=None, pattern=r"^[a-zA-Z0-9_-]+$")]
    tagDisplayName: Annotated[str | None, Field(default=None, pattern=r"^[a-zA-Z0-9_-.]+$")]
    primary: Annotated[bool, Field(default=False)]


class ImageVersion(BaseModel):
    parent: Annotated[BaseModel | None, Field(exclude=True, default=None)]
    name: str
    subpath: str | None
    registries: Annotated[list[Registry], Field(default_factory=list)]
    latest: Annotated[bool, Field(default=False)]
    os: list[ImageVersionOS]

    @model_validator(mode="after")
    def resolve_parentage(self) -> Self:
        for version_os in self.os:
            version_os.parent = self
        return self


class ImageVariant(BaseModel):
    parent: Annotated[BaseModel | None, Field(exclude=True, default=None)]
    name: str
    extension: Annotated[
        str, Field(default=lambda data: data["name"], validate_default=True, pattern=r"^[a-zA-Z0-9_-]+$")
    ]
    tags: Annotated[list[TagPattern], Field(default_factory=list)]
    options: Annotated[list[ToolOptions], ToolField(default_factory=default_tool_options)]


def default_image_variants(parent: BaseModel) -> list[ImageVariant]:
    return [
        ImageVariant(name="std"),
        ImageVariant(name="min"),
    ]


class Image(BaseModel):
    parent: Annotated[BaseModel | None, Field(exclude=True, default=None)]
    name: str
    subpath: str | None
    registries: Annotated[list[Registry], Field(default_factory=list)]
    tags: Annotated[list[TagPattern], Field(default_factory=default_tag_patterns)]
    variants: list[ImageVariant]
    versions: list[ImageVersion]

    @model_validator(mode="after")
    def resolve_parentage(self) -> Self:
        for variant in self.variants:
            variant.parent = self
        for version in self.versions:
            version.parent = self
            for os in version.os:
                os.parent = version
        return self
