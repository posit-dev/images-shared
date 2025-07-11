from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


class TagPatternFilter(str, Enum):
    ALL = "all"
    LATEST = "latest"
    PRIMARY_OS = "primaryOS"
    STD_VARIANT = "stdVariant"


class TagPattern(BaseModel):
    patterns: list[str]
    only: Annotated[list[TagPatternFilter], Field(default_factory=lambda: list[TagPatternFilter.ALL])]


def default_tag_patterns() -> list[TagPattern]:
    return [
        TagPattern(
            patterns=["{{ Version }}-{{ OS }}-{{ Variant }}"],
            only=[TagPatternFilter.ALL],
        ),
        TagPattern(
            patterns=["{{ Version }}-{{ Variant }}"],
            only=[TagPatternFilter.PRIMARY_OS],
        ),
        TagPattern(
            patterns=["{{ Version }}-{{ OS }}"],
            only=[TagPatternFilter.STD_VARIANT],
        ),
        TagPattern(
            patterns=["{{ Version }}"],
            only=[TagPatternFilter.PRIMARY_OS, TagPatternFilter.STD_VARIANT],
        ),
        TagPattern(
            patterns=["{{ OS }}-{{ Variant }}"],
            only=[TagPatternFilter.LATEST],
        ),
        TagPattern(
            patterns=["{{ OS }}"],
            only=[TagPatternFilter.LATEST, TagPatternFilter.STD_VARIANT],
        ),
        TagPattern(
            patterns=["{{ Variant }}"],
            only=[TagPatternFilter.LATEST, TagPatternFilter.PRIMARY_OS],
        ),
        TagPattern(
            patterns=["latest"],
            only=[TagPatternFilter.LATEST, TagPatternFilter.PRIMARY_OS, TagPatternFilter.STD_VARIANT],
        ),
    ]
