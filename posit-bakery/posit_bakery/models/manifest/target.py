import re
from typing import List

from pydantic import BaseModel, field_validator

from posit_bakery.models.manifest.goss import ManifestGoss


# To standardize our images, we will only allow a subset of the regexes
# https://github.com/containers/image/blob/main/docker/reference/regexp.go

# Only allow lowercase letters, number, hyphens, underscores, and periods
# Do not use raw strings here to avoid escaping (e.g. r"{{.+?}}")
TAG_STR: str = "[a-z0-9-_.]"
RE_TAG_STR: re.Pattern = re.compile("^" + TAG_STR + "+$")
# Allow for Jinja2 template in tags
RE_TAG_JINJA: re.Pattern = re.compile("^((?P<jinja>{{.+?}})|" + TAG_STR + ")+$")


class ManifestTarget(BaseModel):
    tags: List[str] = []
    latest_tags: List[str] = []
    goss: ManifestGoss = None
    # Declare containferfile extension

    @classmethod
    def _valid_tag_str(cls, tag: str) -> bool:
        """Check if a tag is a valid string

        :param tag: Tag to check
        """
        return len(tag) <= 128 and RE_TAG_STR.match(tag)

    @classmethod
    def _valid_tag_jinja(cls, tag: str) -> bool:
        """Check if tag contains valid Jinja2

        Since the regex also matches valid string tags, we need to check whether
        the match actually includes Jinja2.

        :param tag: Tag to check
        """
        j2 = RE_TAG_JINJA.match(tag)
        return j2 and j2.groupdict().get("jinja")

    @field_validator("tags", "latest_tags", mode="after")
    @classmethod
    def validate_tags(cls, tags: List[str]) -> List[str]:
        """Ensure tags are short enough and match the expected format"""
        invalid_tags: List[str] = []
        for tag in tags:
            if cls._valid_tag_str(tag) or cls._valid_tag_jinja(tag):
                continue
            invalid_tags.append(tag)

        if len(invalid_tags) > 0:
            invalid_tags = [f"'{t}'" for t in invalid_tags]
            raise ValueError(f"Tags do not match the expected format: {', '.join([t for t in invalid_tags])}")

        return tags
