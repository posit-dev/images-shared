from pydantic import BaseModel, field_validator

from posit_bakery.config.image.posit_product.const import ReleaseChannelEnum


class DevBuildSpec(BaseModel):
    """Typed payload for a workflow-dispatched dev build."""

    version: str
    channel: ReleaseChannelEnum | None = None

    @field_validator("version")
    @classmethod
    def version_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("version must not be empty")
        return v
