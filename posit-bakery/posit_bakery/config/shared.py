import abc

from pydantic import BaseModel, ConfigDict


class BakeryYAMLModel(BaseModel):
    model_config = ConfigDict(validate_assignment=True)


class BakeryPathMixin:
    @property
    @abc.abstractmethod
    def path(self) -> str:
        """Returns the path to the model's directory."""
        raise NotImplementedError("Subclasses must implement the 'path' property.")
