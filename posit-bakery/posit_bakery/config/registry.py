from typing import Annotated

from pydantic import BaseModel, Field, computed_field


class Registry(BaseModel):
    host: str
    namespace: Annotated[str | None, Field(default=None)]

    @computed_field
    @property
    def base_url(self) -> str:
        """Get the base URL for the registry"""
        u: str = f"{self.host}"
        if self.namespace:
            u = f"{u}/{self.namespace}"
        return u

    def __hash__(self) -> int:
        """Unique hash for a ConfigRegistry object"""
        return hash(self.base_url)
