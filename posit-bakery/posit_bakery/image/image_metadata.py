import json
from pathlib import Path
from typing import Annotated, Self

from pydantic import ConfigDict, BaseModel, Field, model_validator


class ImageToolsInspectionPlatformMetadata(BaseModel):
    """Representation of platform metadata from image-tools."""

    model_config = ConfigDict(extra="allow")

    architecture: Annotated[str | None, Field(description="The architecture of the built image.", default=None)]
    os: Annotated[str | None, Field(description="The operating system of the built image.", default=None)]

    def __str__(self):
        """Returns a string representation of the platform."""
        s = ""
        if self.os:
            s += self.os + "/"
        if self.architecture:
            s += self.architecture

        s = s.rstrip("/")

        return s


class ImageToolsInspectionMetadata(BaseModel):
    """Representation of image inspection metadata from image-tools."""

    model_config = ConfigDict(extra="allow")

    media_type: Annotated[
        str | None, Field(description="The media type of the built image.", alias="mediaType", default=None)
    ]
    digest: Annotated[str | None, Field(description="The digest of the built image.", default=None)]
    size: Annotated[int | None, Field(description="The size of the built image in bytes.", default=None)]
    platform: Annotated[
        ImageToolsInspectionPlatformMetadata | None, Field(description="The platform of the built image.", default=None)
    ]
    manifests: Annotated[
        list["ImageToolsInspectionMetadata"],
        Field(description="The manifests of the built image.", default_factory=list),
    ]


class BuildMetadataContainerImageDescriptorPlatform(BaseModel):
    """Representation of a container image platform in build metadata."""

    model_config = ConfigDict(extra="allow")

    architecture: Annotated[str | None, Field(description="The architecture of the built image.", default=None)]
    os: Annotated[str | None, Field(description="The operating system of the built image.", default=None)]


class BuildMetadataContainerImageDescriptor(BaseModel):
    """Representation of a container image descriptor in build metadata."""

    model_config = ConfigDict(extra="allow")

    media_type: Annotated[
        str | None, Field(description="The media type of the built image.", alias="mediaType", default=None)
    ]
    digest: Annotated[str | None, Field(description="The digest of the built image.", default=None)]
    size: Annotated[int | None, Field(description="The size of the built image in bytes.", default=None)]
    annotations: Annotated[
        dict[str, str] | None,
        Field(description="The annotations of the built image.", default=None),
    ]
    platform: Annotated[
        BuildMetadataContainerImageDescriptorPlatform | None,
        Field(description="The platform of the built image.", default=None),
    ]


class BuildMetadata(BaseModel):
    """Representation of build metadata produced by Docker builds."""

    model_config = ConfigDict(extra="allow")

    image_name: Annotated[
        str | None, Field(description="The name of the built image.", alias="image.name", default=None)
    ]
    container_image_digest: Annotated[
        str | None, Field(description="The digest of the built image.", alias="containerimage.digest", default=None)
    ]
    container_image_descriptor: Annotated[
        BuildMetadataContainerImageDescriptor | None,
        Field(
            description="The descriptor of the built image.",
            alias="containerimage.descriptor",
            default=None,
        ),
    ]

    @property
    def image_tags(self) -> list[str]:
        """Returns the list of tags associated with the built image."""
        tags = self.image_name.split(",")
        return [tag.strip() for tag in tags if tag.strip()]

    @property
    def image_ref(self) -> str | None:
        """Returns the full image reference including name and digest."""
        primary_tag = self.image_tags[0]
        if primary_tag and self.container_image_digest:
            return f"{primary_tag}@{self.container_image_digest}"
        elif primary_tag:
            return primary_tag
        return None


class MetadataFile(BaseModel):
    target_uid: Annotated[str, Field(description="The target UID associated with the metadata.")]
    filepath: Annotated[Path | None, Field(description="The path to the metadata file.", default=None)]
    metadata: Annotated[BuildMetadata | None, Field(description="The build metadata.", default=None)]

    @model_validator(mode="after")
    def validate_metadata(self) -> Self:
        """Validates that metadata is provided."""
        if self.metadata is None:
            if self.filepath is None or not self.filepath.is_file():
                raise ValueError("Either filepath or metadata must be provided.")
            with open(self.filepath, "r") as f:
                content = json.load(f)
                if not isinstance(content, dict):
                    raise ValueError("The metadata file does not contain a valid JSON object.")
                if self.target_uid in content.keys():
                    content = content[self.target_uid]
                self.metadata = BuildMetadata.model_validate(content, by_alias=True)

        return self
