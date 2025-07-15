import abc

from pydantic import BaseModel


class ToolOptions(BaseModel, abc.ABC):
    tool: str
