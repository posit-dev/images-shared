import json
from pathlib import Path
from typing import Annotated, Any

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


class MetadataFile:
    def __init__(
        self, target_uid: str, filepath: Path | None = None, metadata: BuildMetadata | dict[str, Any] | None = None
    ):
        """Initializes a MetadataFile instance.

        Args:
            filepath: The path to the metadata file.
            metadata: The build metadata as a BuildMetadata instance or a dictionary.
        """
        if filepath is None and metadata is None:
            raise ValueError("Either filepath or metadata must be provided.")

        self.target_uid = target_uid
        self._filepath = filepath

        if isinstance(metadata, BuildMetadata):
            self.metadata = metadata
        elif isinstance(metadata, dict):
            self.metadata = BuildMetadata.model_validate(metadata)
        elif metadata is not None:
            raise TypeError("metadata must be a BuildMetadata instance or a dictionary")

        if self._filepath and self._filepath.is_file():
            self._reload()
        elif self._filepath is not None:
            raise ValueError("The provided filepath is not a valid file.")

    def _reload(self):
        """Reloads the metadata from the file."""
        with open(self._filepath, "r") as f:
            content = json.load(f)
            if not isinstance(content, dict):
                raise ValueError("The metadata file does not contain a valid JSON object.")
            if self.target_uid in content.keys():
                content = content[self.target_uid]
            self.metadata = BuildMetadata.model_validate(content)

    @property
    def filepath(self):
        """Returns the path to the metadata file."""
        return self._filepath

    @filepath.setter
    def filepath(self, value: Path):
        """Sets the path to the metadata file and reloads the metadata."""
        if not value or not value.is_file():
            raise ValueError("The provided filepath is not a valid file.")
        self._filepath = value
        self._reload()
