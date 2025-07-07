from typing import List

from pydantic import BaseModel, ConfigDict, field_validator

from posit_bakery.models.image.tags import is_tag_valid
from posit_bakery.models.manifest.goss import ManifestGoss


class ManifestTarget(BaseModel):
    model_config = ConfigDict(frozen=True)

    tags: List[str] = []
    latest_tags: List[str] = []
    goss: ManifestGoss = ManifestGoss()
    # Declare containferfile extension

    @field_validator("tags", "latest_tags", mode="after")
    @classmethod
    def validate_tags(cls, tags: List[str]) -> List[str]:
        """Ensure tags are short enough and match the expected format"""
        invalid_tags: List[str] = []
        for tag in tags:
            if is_tag_valid(tag):
                continue
            invalid_tags.append(tag)

        if len(invalid_tags) > 0:
            invalid_tags = [f"'{t}'" for t in invalid_tags]
            raise ValueError(f"Tags do not match the expected format: {', '.join([t for t in invalid_tags])}")

        return tags
