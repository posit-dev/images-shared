import logging
from typing import List

from pydantic import BaseModel, ConfigDict, field_validator

from posit_bakery.models.manifest import find_os

log = logging.getLogger(__name__)


class ManifestBuild(BaseModel):
    model_config = ConfigDict(frozen=True)

    # version is part of the title
    os: List[str]  # Supported OSes, validate with mapping
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
