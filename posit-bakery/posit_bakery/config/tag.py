from enum import Enum
from typing import Annotated

from pydantic import Field

from posit_bakery.config.shared import BakeryYAMLModel


# TODO: Consider how to implement filter logic either as part of TagPattern or as part of images
class TagPatternFilter(str, Enum):
    ALL = "all"
    LATEST = "latest"
    PRIMARY_OS = "primaryOS"
    PRIMARY_VARIANT = "primaryVariant"


class TagPattern(BakeryYAMLModel):
    patterns: list[str]
    only: Annotated[list[TagPatternFilter], Field(default_factory=lambda: [TagPatternFilter.ALL])]

    def render(self, **kwargs) -> list[str]:
        """Render the Jinja2 tag patterns with the provided keyword arguments."""
        from jinja2 import Template

        rendered_tags = []
        for pattern in self.patterns:
            template = Template(pattern)
            tag = template.render(**kwargs)

            rendered_tags.append(tag)
        return rendered_tags

    def __hash__(self):
        """Hash the TagPattern based on its patterns and only fields."""
        return hash((tuple(self.patterns), tuple(self.only)))


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
            only=[TagPatternFilter.PRIMARY_VARIANT],
        ),
        TagPattern(
            patterns=["{{ Version }}"],
            only=[TagPatternFilter.PRIMARY_OS, TagPatternFilter.PRIMARY_VARIANT],
        ),
        TagPattern(
            patterns=["{{ OS }}-{{ Variant }}"],
            only=[TagPatternFilter.LATEST],
        ),
        TagPattern(
            patterns=["{{ OS }}"],
            only=[TagPatternFilter.LATEST, TagPatternFilter.PRIMARY_VARIANT],
        ),
        TagPattern(
            patterns=["{{ Variant }}"],
            only=[TagPatternFilter.LATEST, TagPatternFilter.PRIMARY_OS],
        ),
        TagPattern(
            patterns=["latest"],
            only=[TagPatternFilter.LATEST, TagPatternFilter.PRIMARY_OS, TagPatternFilter.PRIMARY_VARIANT],
        ),
    ]
