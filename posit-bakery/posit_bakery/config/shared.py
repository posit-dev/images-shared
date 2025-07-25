import abc

from pydantic import BaseModel


class BakeryBaseModel(BaseModel, abc.ABC):
    @property
    @abc.abstractmethod
    def path(self) -> str:
        """Returns the path to the model's directory."""
        raise NotImplementedError("Subclasses must implement the 'path' property.")
