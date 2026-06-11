from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from posit_bakery.config.image.posit_product.const import CALVER_REGEX_PATTERN, ReleaseChannelEnum


class DevBuildSpec(BaseModel):
    """Typed payload for a dev build — either a dispatch-pinned version or a
    branch-targeted discovery build. At least one of version or release_branch
    must be set."""

    model_config = ConfigDict(extra="forbid")

    version: str | None = None
    channel: ReleaseChannelEnum | None = None
    release_branch: str | None = None

    @field_validator("version")
    @classmethod
    def version_not_empty(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("version must not be empty")
        if not CALVER_REGEX_PATTERN.fullmatch(v):
            raise ValueError(f"version {v!r} is not a valid CalVer string (e.g. '2026.06.0-daily+143')")
        return v

    @field_validator("release_branch")
    @classmethod
    def release_branch_not_empty(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("release_branch must not be empty")
        return v

    @model_validator(mode="after")
    def require_version_or_release_branch(self) -> Self:
        if self.version is None and self.release_branch is None:
            raise ValueError("at least one of 'version' or 'release_branch' must be set")
        return self
