from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator, computed_field

from posit_bakery.config.registry import Registry
from posit_bakery.config.shared import BakeryBaseModel
from posit_bakery.config.tag import TagPattern, default_tag_patterns
from posit_bakery.config.tools import ToolField, default_tool_options


class ImageVersionOS(BaseModel):
    parent: Annotated[Union[BakeryBaseModel, None] | None, Field(exclude=True, default=None)]
    name: str
    extension: Annotated[str | None, Field(default=None, pattern=r"^[a-zA-Z0-9_-]+$")]
    tagDisplayName: Annotated[str | None, Field(default=None, pattern=r"^[a-zA-Z0-9_-.]+$")]
    primary: Annotated[bool, Field(default=False)]


class ImageVersion(BakeryBaseModel):
    parent: Annotated[Union[BakeryBaseModel, None], Field(exclude=True, default=None)]
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

    @computed_field
    @property
    def path(self) -> Path:
        """Returns the path to the image version directory."""
        if self.parent is None or self.parent.path is None:
            raise ValueError("Parent image must resolve a valid path.")
        return Path(self.parent.path) / self.subpath


class ImageVariant(BaseModel):
    parent: Annotated[Union[BakeryBaseModel, None] | None, Field(exclude=True, default=None)]
    name: str
    extension: Annotated[
        str, Field(default=lambda data: data["name"], validate_default=True, pattern=r"^[a-zA-Z0-9_-]+$")
    ]
    tags: Annotated[list[TagPattern], Field(default_factory=list)]
    options: Annotated[list[ToolOptions], ToolField(default_factory=default_tool_options)]
    options: Annotated[list[ToolField], Field(default_factory=default_tool_options)]


def default_image_variants(parent: BaseModel) -> list[ImageVariant]:
    return [
        ImageVariant(name="std"),
        ImageVariant(name="min"),
    ]


class Image(BakeryBaseModel):
    parent: Annotated[Union[BakeryBaseModel, None] | None, Field(exclude=True, default=None)]
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

    @computed_field
    @property
    def path(self) -> Path | None:
        """Returns the path to the image directory."""
        if self.parent is None or self.parent.path is None:
            raise ValueError("Parent BakeryConfig must resolve a valid path.")
        return Path(self.parent.path) / self.subpath
