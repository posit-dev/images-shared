import abc
import re
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, HttpUrl

from posit_bakery.const import REGEX_IMAGE_TAG_SUFFIX_ALLOWED_CHARACTERS_PATTERN


def normalize_https_url(value: Any) -> Any:
    """Prepend 'https://' if no scheme present.

    Allows users to specify URLs like 'example.com' without the scheme.
    """
    if isinstance(value, str) and "://" not in value:
        return f"https://{value}"
    return value


HttpUrlWithDefaultScheme = Annotated[HttpUrl, BeforeValidator(normalize_https_url)]

# Shared field configuration for file extensions.
ExtensionField = Annotated[
    str,
    Field(
        default_factory=lambda data: re.sub(r"[^a-zA-Z0-9_-]", "", data.get("name", "").lower()),
        pattern=r"^[a-zA-Z0-9_-]+$",
        validate_default=True,
    ),
]


# Shared field configuration for tag display names.
TagDisplayNameField = Annotated[
    str,
    Field(
        default_factory=lambda data: re.sub(
            REGEX_IMAGE_TAG_SUFFIX_ALLOWED_CHARACTERS_PATTERN, "-", data.get("name", "").lower()
        ),
        pattern=r"^[a-zA-Z0-9_.-]+$",
        validate_default=True,
    ),
]


class OSFamilyEnum(str, Enum):
    DEBIAN_LIKE = "debian"
    REDHAT_LIKE = "rhel"
    SUSE_LIKE = "sles"
    UNKNOWN = "unknown"


class BakeryYAMLModel(BaseModel):
    """Base model for Bakery configuration models."""

    model_config = ConfigDict(validate_assignment=True)


class BakeryPathMixin:
    """Mixin for models that require a path to their directory."""

    @property
    @abc.abstractmethod
    def path(self) -> Path | None:
        """Returns the path to the model's directory."""
        raise NotImplementedError("Subclasses must implement the 'path' property.")
