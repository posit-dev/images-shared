from typing import List

from pydantic import BaseModel, field_validator

from posit_bakery.models.manifest import find_os


class ManifestBuild(BaseModel):
    # version is part of the title
    os: List[str]  # Supported OSes, validate with mapping
    latest: bool = False
    # optional targets, default to "all"

    @field_validator("os", mode="after")
    @classmethod
    def validate_os(cls, _os: List[str]) -> List[str]:
        for o in _os:
            if not find_os(o):
                raise ValueError(f"Operating system '{o}' is not supported.")

        return _os
