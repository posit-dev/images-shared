import abc
import re
from pathlib import Path

from pydantic import Field
from typing import Annotated

from pydantic import BaseModel, ConfigDict

from posit_bakery.const import REGEX_IMAGE_TAG_SUFFIX_ALLOWED_CHARACTERS_PATTERN

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
