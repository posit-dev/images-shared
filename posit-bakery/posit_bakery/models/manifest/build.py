import logging
from typing import List

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from posit_bakery.models.manifest import find_os

log = logging.getLogger(__name__)


class ManifestBuild(BaseModel):
    model_config = ConfigDict(frozen=True)

    # version is part of the title
    os: List[str]  # Supported OSes, validate with mapping
    primary_os: str = None  # Primary OS for the image
    latest: bool = False
    # optional targets, default to "all"

    @field_validator("os", mode="after")
    @classmethod
    def validate_os(cls, _os: List[str]) -> List[str]:
        for o in _os:
            if not find_os(o):
                log.warning(
                    f"Operating system '{o}' is not in the supported OS list. This may cause unexpected behavior."
                )

        return _os

    @model_validator(mode="before")
    @classmethod
    def validate_primary_os(cls, data: dict) -> dict:
        _os = data.get("os")

        if data.get("primary_os") is None:
            if len(_os) == 1:
                data["primary_os"] = _os[0]
            if len(_os) > 1:
                raise ValueError("Primary OS must be specified if multiple OSes are specified")
        else:
            if data["primary_os"] not in _os:
                raise ValueError("Primary OS must be one of the specified OSes")

        return data
