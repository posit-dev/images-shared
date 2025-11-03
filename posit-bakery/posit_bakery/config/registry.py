from typing import Annotated

from pydantic import ConfigDict, Field

from posit_bakery.config.shared import BakeryYAMLModel


class Registry(BakeryYAMLModel):
    """Model representing an image registry in the Bakery configuration."""

    model_config = ConfigDict(extra="forbid")

    host: Annotated[str, Field(description="Hostname of the registry.", examples=["docker.io", "ghcr.io"])]
    namespace: Annotated[
        str | None,
        Field(default=None, description="Namespace or organization in the registry.", examples=["posit", "myorg"]),
    ]

    @property
    def base_url(self) -> str:
        """Get the base URL for the registry.

        :return: The base URL of the registry, including the namespace if provided.
        """
        u: str = f"{self.host}"
        if self.namespace:
            u = f"{u}/{self.namespace}"
        return u

    def __hash__(self) -> int:
        """Unique hash for a Registry object."""
        return hash(self.base_url)


class RegistryImage(Registry):
    """Model representing an image from a registry in the Bakery configuration."""

    name: Annotated[
        str,
        Field(description="Name of the image repository.", examples=["connect", "package-manager"]),
    ]
