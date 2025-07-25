import re
from copy import deepcopy
from pathlib import Path
from typing import Annotated, Self, Union

from pydantic import BaseModel, Field, model_validator, computed_field

from posit_bakery.config.registry import Registry
from posit_bakery.config.shared import BakeryBaseModel
from posit_bakery.config.tag import TagPattern, default_tag_patterns
from posit_bakery.config.tools import ToolField, default_tool_options


class ImageVersionOS(BaseModel):
    parent: Annotated[Union[BakeryBaseModel, None] | None, Field(exclude=True, default=None)]
    name: str
    primary: Annotated[bool, Field(default=False)]
    # These fields are not set as annotations because it turns off syntax highlighting for the lambda in some editors.
    extension: str = Field(
        default_factory=lambda data: re.sub(r"[^a-zA-Z0-9_-]", "", data["name"].lower()),
        pattern=r"^[a-zA-Z0-9_-]+$",
        validate_default=True,
    )
    tagDisplayName: str = Field(
        default_factory=lambda data: re.sub(r"[^a-zA-Z0-9_\-.]", "-", data["name"].lower()),
        pattern=r"^[a-zA-Z0-9_.-]+$",
        validate_default=True,
    )


class ImageVersion(BakeryBaseModel):
    parent: Annotated[Union[BakeryBaseModel, None], Field(exclude=True, default=None)]
    name: str
    subpath: Annotated[str, Field(default_factory=lambda data: data["name"])]
    registries: Annotated[list[Registry], Field(default_factory=list)]
    latest: Annotated[bool, Field(default=False)]
    os: Annotated[list[ImageVersionOS], Field(default_factory=list)]

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

    @computed_field
    @property
    def merged_registries(self) -> list[Registry]:
        """Returns the merged registries for this image version."""
        all_registries = deepcopy(self.registries)
        if self.parent is not None and isinstance(self.parent, Image):
            for registry in self.parent.merged_registries:
                if registry not in all_registries:
                    all_registries.append(registry)
        return all_registries


class ImageVariant(BaseModel):
    parent: Annotated[Union[BakeryBaseModel, None] | None, Field(exclude=True, default=None)]
    name: str
    extension: str = Field(
        default_factory=lambda data: re.sub(r"[^a-zA-Z0-9_-]", "", data["name"].lower()),
        pattern=r"^[a-zA-Z0-9_-]+$",
        validate_default=True,
    )
    tagDisplayName: str = Field(
        default_factory=lambda data: re.sub(r"[^a-zA-Z0-9_\-.]", "-", data["name"].lower()),
        pattern=r"^[a-zA-Z0-9_.-]+$",
        validate_default=True,
    )
    tagPatterns: Annotated[list[TagPattern], Field(default_factory=list)]
    options: Annotated[list[ToolField], Field(default_factory=default_tool_options)]


def default_image_variants() -> list[ImageVariant]:
    return [
        ImageVariant(name="Standard", extension="std", tagDisplayName="std"),
        ImageVariant(name="Minimal", extension="min", tagDisplayName="min"),
    ]


class Image(BakeryBaseModel):
    parent: Annotated[Union[BakeryBaseModel, None] | None, Field(exclude=True, default=None)]
    name: str
    subpath: Annotated[str, Field(default_factory=lambda data: data["name"])]
    registries: Annotated[list[Registry], Field(default_factory=list)]
    tagPatterns: Annotated[list[TagPattern], Field(default_factory=default_tag_patterns)]
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

    @computed_field
    @property
    def merged_registries(self) -> list[Registry]:
        """Returns the merged registries for this image."""
        all_registries = deepcopy(self.registries)
        if self.parent is not None:
            for registry in self.parent.registries:
                if registry not in all_registries:
                    all_registries.append(registry)
        return all_registries
