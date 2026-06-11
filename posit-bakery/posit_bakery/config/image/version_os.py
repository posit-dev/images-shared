import logging
import re
from typing import Annotated, Union

from pydantic import BaseModel, Field, field_validator, field_serializer
from pydantic_core.core_schema import ValidationInfo

from posit_bakery.config.shared import BakeryYAMLModel
from posit_bakery.const import (
    REGEX_IMAGE_TAG_SUFFIX_ALLOWED_CHARACTERS_PATTERN,
    REGEX_OS_EXTENSION_PATTERN,
    REGEX_OS_TAG_DISPLAY_NAME_PATTERN,
)
from .build_os import BuildOS, SUPPORTED_OS, ALTERNATE_NAMES, TargetPlatform, DEFAULT_PLATFORMS
from .posit_product.const import URL_WITH_ENV_VARS_REGEX_PATTERN

_OSLESS_NAMES = frozenset({"scratch"})

log = logging.getLogger(__name__)

_NAME_VERSION_PATTERN = re.compile(r"(?P<name>[\D]+)(?P<version>[\d.]*)")


def _resolve_name_to_build_os(name: str) -> BuildOS:
    name = name.lower().strip()
    match = _NAME_VERSION_PATTERN.match(name)
    if not match:
        log.warning(f"Could not identify '{name}' as a supported OS.")
        return SUPPORTED_OS["unknown"]
    match_dict = match.groupdict()
    match_dict["name"] = match_dict.get("name", "").strip().rstrip("-")

    if match_dict["name"] in ALTERNATE_NAMES:
        match_dict["name"] = ALTERNATE_NAMES[match_dict["name"]]

    if not match_dict.get("version"):
        if match_dict["name"] in SUPPORTED_OS:
            if isinstance(SUPPORTED_OS.get(match_dict["name"]), BuildOS):
                return SUPPORTED_OS[match_dict["name"]]
            else:
                # Convert to int before max() to get numeric ordering (9 < 10), not lexical ("9" > "10")
                latest = str(max([int(x) for x in SUPPORTED_OS[match_dict["name"]].keys()]))
                return SUPPORTED_OS[match_dict["name"]][latest]
    else:
        match_dict["version"] = match_dict.get("version", "").split(".")[0]
        if match_dict["name"] in SUPPORTED_OS and match_dict["version"] in SUPPORTED_OS.get(match_dict["name"]):
            return SUPPORTED_OS[match_dict["name"]][match_dict["version"]]

    return SUPPORTED_OS["unknown"]


class ImageVersionOS(BakeryYAMLModel):
    """Model representing a supported operating system for an image version."""

    parent: Annotated[
        Union[BaseModel, None] | None, Field(exclude=True, default=None, description="Parent ImageVersion object.")
    ]
    name: Annotated[
        str,
        Field(
            description="The operating system human readable name and version string.",
            examples=["Ubuntu 22.04", "Debian 12"],
        ),
    ]
    primary: Annotated[
        bool, Field(default=False, description="Flag to indicate if this is the primary OS for the image.")
    ]
    platforms: Annotated[
        list[TargetPlatform],
        Field(default=DEFAULT_PLATFORMS, description="List of platforms to build for this image."),
    ]
    extension: Annotated[
        str,
        Field(
            default_factory=lambda data: (
                ""
                if data.get("name", "").lower().strip() in _OSLESS_NAMES
                else re.sub(r"[^a-zA-Z0-9_-]", "", data.get("name", "").lower())
            ),
            pattern=REGEX_OS_EXTENSION_PATTERN,
            validate_default=True,
            description="File extension used in the Containerfile filename in the pattern "
            "Containerfile.<os>.<variant> for this OS. Set to an empty string if no extension is needed.",
            examples=["ubuntu2204", "debian12"],
        ),
    ]
    tagDisplayName: Annotated[
        str,
        Field(
            default_factory=lambda data: (
                ""
                if data.get("name", "").lower().strip() in _OSLESS_NAMES
                else re.sub(REGEX_IMAGE_TAG_SUFFIX_ALLOWED_CHARACTERS_PATTERN, "-", data.get("name", "").lower())
            ),
            pattern=REGEX_OS_TAG_DISPLAY_NAME_PATTERN,
            validate_default=True,
            description="The name used in image tags for this OS. This is used to create the tag "
            "in the format <image>:<version>-<os>-<variant>.",
            examples=["ubuntu-22.04", "debian-12"],
        ),
    ]
    buildOS: Annotated[
        BuildOS,
        Field(
            default=SUPPORTED_OS["unknown"],
            description="Auto-populated additional metadata about this OS. Sets to 'unknown' if the OS could not be "
            "identified as a supported OS.",
            exclude=True,
            validate_default=True,
        ),
    ]
    artifactDownloadURL: Annotated[
        str | None,
        Field(
            default=None,
            description="Optional URL for artifact retrieval. Passed to version template rendering.",
            pattern=URL_WITH_ENV_VARS_REGEX_PATTERN,
        ),
    ]
    artifactOs: Annotated[
        str | None,
        Field(
            default=None,
            description="OS name for artifact download URL resolution when this OS cannot "
            "resolve artifacts directly (e.g. scratch).",
        ),
    ]

    def __hash__(self):
        """Unique hash for an ImageVersionOS object."""
        return hash((self.name, self.extension, self.tagDisplayName))

    def __eq__(self, other):
        """Equality check for ImageVersionOS based on name.

        :param other: The other object to compare against.
        """
        if isinstance(other, ImageVersionOS):
            return hash(self) == hash(other)
        return False

    @field_validator("artifactOs", mode="after")
    @classmethod
    def validate_artifact_os(cls, value: str | None) -> str | None:
        if value is None:
            return None
        resolved = _resolve_name_to_build_os(value)
        if resolved == SUPPORTED_OS["unknown"]:
            raise ValueError(f"artifactOs '{value}' is not a recognized OS name")
        return value

    @field_validator("buildOS", mode="after")
    @classmethod
    def populate_build_os(cls, value: BuildOS, info: ValidationInfo) -> BuildOS:
        """Populates the buildOS field from the name field."""
        if isinstance(value, BuildOS) and value != SUPPORTED_OS["unknown"]:
            return value
        name = info.data.get("name")
        if name is None:
            return SUPPORTED_OS["unknown"]
        return _resolve_name_to_build_os(name)

    @field_serializer("platforms")
    def serialize_platforms(self, platforms: list[TargetPlatform]) -> list[str]:
        """Serialize the platforms field to a list of strings for YAML output."""
        return [platform.value for platform in platforms]

    @property
    def artifact_build_os(self) -> BuildOS:
        if self.artifactOs is not None:
            return _resolve_name_to_build_os(self.artifactOs)
        return self.buildOS
