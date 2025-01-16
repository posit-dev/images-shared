from pydantic import BaseModel


class ConfigRegistry(BaseModel):
    """Configuration for a container image registry

    Used for tagging of images and pushing to the registry
    """

    host: str
    namespace: str | None = None

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
