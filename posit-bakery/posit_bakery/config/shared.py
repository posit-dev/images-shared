import abc
import re
from pydantic import Field
from typing import Annotated

from pydantic import BaseModel, ConfigDict


ExtensionField = Annotated[
    str,
    Field(
        default_factory=lambda data: re.sub(r"[^a-zA-Z0-9_-]", "", data["name"].lower()),
        pattern=r"^[a-zA-Z0-9_-]+$",
        validate_default=True,
    ),
]


TagDisplayNameField = Annotated[
    str,
    Field(
        default_factory=lambda data: re.sub(r"[^a-zA-Z0-9_\-.]", "-", data["name"].lower()),
        pattern=r"^[a-zA-Z0-9_.-]+$",
        validate_default=True,
    ),
]


class BakeryYAMLModel(BaseModel):
    model_config = ConfigDict(validate_assignment=True)


class BakeryPathMixin:
    @property
    @abc.abstractmethod
    def path(self) -> str:
        """Returns the path to the model's directory."""
        raise NotImplementedError("Subclasses must implement the 'path' property.")
