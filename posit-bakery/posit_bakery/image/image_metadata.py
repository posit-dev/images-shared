from typing import Annotated

from pydantic import ConfigDict, BaseModel, Field, computed_field


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

    @computed_field
    @property
    def image_ref(self) -> str | None:
        """Returns the full image reference including name and digest."""
        if self.image_name and self.container_image_digest:
            return f"{self.image_name}@{self.container_image_digest}"
        elif self.image_name:
            return self.image_name
        return None
