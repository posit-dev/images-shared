import logging
import re
from typing import Annotated, Union

from pydantic import BaseModel, Field, field_validator, HttpUrl
from pydantic_core.core_schema import ValidationInfo

from .build_os import BuildOS, SUPPORTED_OS, ALTERNATE_NAMES
from posit_bakery.config.shared import BakeryYAMLModel, ExtensionField, TagDisplayNameField

log = logging.getLogger(__name__)


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
    extension: Annotated[
        ExtensionField,
        Field(
            description="File extension used in the Containerfile filename in the pattern "
            "Containerfile.<os>.<variant> for this OS. Set to an empty string if no extension is needed.",
            examples=["ubuntu2204", "debian12"],
        ),
    ]
    tagDisplayName: Annotated[
        TagDisplayNameField,
        Field(
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
        HttpUrl | None,
        Field(default=None, description="Optional URL for artifact retrieval. Passed to version template rendering."),
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

    @field_validator("buildOS", mode="after")
    @classmethod
    def populate_build_os(cls, value: BuildOS, info: ValidationInfo) -> BuildOS:
        """Populates the build_os field based on the name field. If the OS cannot be determined, it defaults to unknown."""
        # If the buildOS is already set to a known value, return it directly.
        if isinstance(value, BuildOS) and value != SUPPORTED_OS["unknown"]:
            return value

        name_pattern = re.compile(r"(?P<name>[\D]+)(?P<version>[\d.]*)")
        name = info.data.get("name")
        if name is None:
            return SUPPORTED_OS["unknown"]

        name = name.lower().strip()
        match = name_pattern.match(name)
        if not match:
            log.warning(f"Could not identify '{name}' as a supported OS.")
            return SUPPORTED_OS["unknown"]
        match_dict = match.groupdict()
        match_dict["name"] = match_dict.get("name", "").strip()

        # Handle possible alternate names for some OSes.
        if match_dict["name"] in ALTERNATE_NAMES:
            match_dict["name"] = ALTERNATE_NAMES[match_dict["name"]]

        # Ideally, a name and version should be in the name field. If not, we try to infer an unversioned OS
        # (such as scratch) or default to the latest version of a known OS.
        if not match_dict.get("version"):
            if match_dict["name"] in SUPPORTED_OS:
                # If only the name is provided and it's an unversioned OS, use it.
                if isinstance(SUPPORTED_OS.get(match_dict["name"]), BuildOS):
                    return SUPPORTED_OS[match_dict["name"]]
                # Otherwise, use the latest version of the matching OS name if possible.
                else:
                    # This line converts each version of the OS from a string to an int, finds the max, then converts it
                    # back to a string. This ensures that we get the latest version numerically, not lexically.
                    latest = str(max([int(x) for x in SUPPORTED_OS[match_dict["name"]].keys()]))
                    return SUPPORTED_OS[match_dict["name"]][latest]
        # Otherwise, assume a two-part name and version in the name field.
        else:
            match_dict["version"] = match_dict.get("version", "").split(".")[0]
            # Check if the name and version are in the supported OS list.
            if match_dict["name"] in SUPPORTED_OS and match_dict["version"] in SUPPORTED_OS.get(match_dict["name"]):
                return SUPPORTED_OS[match_dict["name"]][match_dict["version"]]

        return SUPPORTED_OS["unknown"]
