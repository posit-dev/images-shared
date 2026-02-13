import datetime
import json
import logging
from pathlib import Path
from typing import Annotated, Self

from pydantic import ConfigDict, BaseModel, Field, RootModel

log = logging.getLogger(__name__)


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


class BuildMetadataBuildProvenanceMaterial(BaseModel):
    """Representation of a material used in the build process."""

    model_config = ConfigDict(extra="allow")

    uri: Annotated[str | None, Field(description="The URI of the material.", default=None)]
    digest: Annotated[dict[str, str] | None, Field(description="The digest of the material.", default=None)]


class BuildMetadataBuildProvenanceInvocation(BaseModel):
    """Representation of the invocation of the build process."""

    model_config = ConfigDict(extra="allow")

    config_source: Annotated[
        dict,
        Field(
            description="The configuration source of the build invocation.", alias="configSource", default_factory=dict
        ),
    ]
    parameters: Annotated[dict, Field(description="The parameters of the build invocation.", default_factory=dict)]
    environment: Annotated[dict, Field(description="The environment of the build invocation.", default_factory=dict)]


class BuildMetadataBuildProvenance(BaseModel):
    """Representation of build provenance in build metadata."""

    model_config = ConfigDict(extra="allow")

    builder: Annotated[dict, Field(description="The builder used to build the image.", default_factory=dict)]
    build_type: Annotated[
        str | None, Field(description="The type of build performed.", alias="buildType", default=None)
    ]
    materials: Annotated[
        list[BuildMetadataBuildProvenanceMaterial],
        Field(description="The materials used in the build process.", default_factory=list),
    ]
    invocation: Annotated[
        BuildMetadataBuildProvenanceInvocation | None,
        Field(description="The invocation of the build process.", default=None),
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
    build_provenance: Annotated[
        BuildMetadataBuildProvenance | None,
        Field(description="The build provenance of the built image.", alias="buildx.build.provenance", default=None),
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

    @property
    def created_at(self) -> datetime.datetime:
        """Returns the creation timestamp of the built image if available."""
        if self.container_image_descriptor and self.container_image_descriptor.annotations:
            dt_str = self.container_image_descriptor.annotations.get("org.opencontainers.image.created")
            if dt_str:
                try:
                    return datetime.datetime.fromisoformat(dt_str)
                except ValueError:
                    pass
        if self.build_provenance:
            # If the creation timestamp is not available in the annotations, we can use the build start time from
            # labels.
            if self.build_provenance.invocation and self.build_provenance.invocation.parameters:
                start_time_str = self.build_provenance.invocation.parameters.get("args", {}).get(
                    "label:org.opencontainers.image.created"
                )
                if start_time_str:
                    try:
                        return datetime.datetime.fromisoformat(start_time_str)
                    except ValueError:
                        pass
        log.debug("Creation timestamp not found in metadata, defaulting to current time.")
        return datetime.datetime.now()

    @property
    def platform(self) -> str | None:
        """Returns the platform of the built image if available."""
        # First, check the platform information in the container image descriptor, as it is more likely to be accurate
        # for multi-platform builds.
        if self.container_image_descriptor and self.container_image_descriptor.platform:
            platform = self.container_image_descriptor.platform
            if platform.os and platform.architecture:
                return f"{platform.os}/{platform.architecture}"
        # If platform information is not available in the container image descriptor, we can check the build provenance
        # invocation environment as that should match the image platform when unspecified.
        if self.build_provenance and self.build_provenance.invocation and self.build_provenance.invocation.environment:
            platform = self.build_provenance.invocation.environment.get("platform")
            if platform:
                return platform

        return None


class BuildMetadataMap(RootModel[dict[str, BuildMetadata]]):
    """Representation of a mapping from target UIDs to build metadata."""


class MetadataFile(BaseModel):
    filepath: Annotated[Path | None, Field(description="The path to the metadata file.", default=None)]
    metadata_map: Annotated[BuildMetadataMap, Field(description="The build metadata.")]

    def __repr__(self):
        """Returns a string representation of the metadata file."""
        return f"MetadataFile(filepath={self.filepath.absolute()}, metadata_map={self.metadata_map})"

    @classmethod
    def load(cls, filepath: Path) -> Self:
        """Creates a MetadataFile instance from a JSON file."""
        if not filepath.is_file():
            raise FileNotFoundError(f"Metadata file '{str(filepath)}' does not exist.")

        with open(filepath, "r") as f:
            data = json.load(f)

        metadata_map = BuildMetadataMap.model_validate(data)
        return cls(filepath=filepath, metadata_map=metadata_map)

    @classmethod
    def loads(cls, json_str: str) -> Self:
        """Creates a MetadataFile instance from a JSON string."""
        data = json.loads(json_str)

        metadata_map = BuildMetadataMap.model_validate(data)
        return cls(metadata_map=metadata_map)

    def get_target_metadata_by_uid(self, target_uid: str) -> BuildMetadata | None:
        """Returns the build metadata associated with a given target UID."""
        return self.metadata_map.root.get(target_uid)
