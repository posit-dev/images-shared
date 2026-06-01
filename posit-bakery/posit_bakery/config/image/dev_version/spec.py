from pydantic import BaseModel, ConfigDict, field_validator

from posit_bakery.config.image.posit_product.const import ReleaseChannelEnum


class DevBuildSpec(BaseModel):
    """Typed payload for a workflow-dispatched dev build."""

    model_config = ConfigDict(extra="forbid")

    version: str
    channel: ReleaseChannelEnum | None = None

    @field_validator("version")
    @classmethod
    def version_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("version must not be empty")
        return v
