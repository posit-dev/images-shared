import re
from enum import Enum
from typing import Annotated

from pydantic import Field

from posit_bakery.config.shared import BakeryYAMLModel
from posit_bakery.config.templating.filters import jinja2_env


# TODO: Consider how to implement filter logic either as part of TagPattern or as part of images
class TagPatternFilter(str, Enum):
    ALL = "all"
    LATEST = "latest"
    PRIMARY_OS = "primaryOS"
    PRIMARY_VARIANT = "primaryVariant"


class TagPattern(BakeryYAMLModel):
    patterns: list[Annotated[str, Field(pattern=r"^([a-z0-9-_.]|(?P<jinja>\{{2}.+?}{2}))+$")]]
    only: Annotated[list[TagPatternFilter], Field(default_factory=lambda: [TagPatternFilter.ALL])]

    def render(self, **kwargs) -> list[str]:
        """Render the Jinja2 tag patterns with the provided keyword arguments."""
        rendered_tags = []
        for pattern in self.patterns:
            env = jinja2_env()
            template = env.from_string(pattern)
            tag = template.render(**kwargs)
            tag = tag.strip()
            tag = re.sub(r"[^a-zA-Z0-9_\-.]", "-", tag)  # Ensure tag is safe for use.

            rendered_tags.append(tag)

        return rendered_tags

    def __hash__(self):
        """Hash the TagPattern based on its patterns and only fields."""
        return hash((tuple(self.patterns), tuple(self.only)))


def default_tag_patterns() -> list[TagPattern]:
    return [
        TagPattern(
            patterns=["{{ Version }}-{{ OS }}-{{ Variant }}", "{{ Version | stripMetadata }}-{{ OS }}-{{ Variant }}"],
            only=[TagPatternFilter.ALL],
        ),
        TagPattern(
            patterns=["{{ Version }}-{{ Variant }}", "{{ Version | stripMetadata }}-{{ Variant }}"],
            only=[TagPatternFilter.PRIMARY_OS],
        ),
        TagPattern(
            patterns=["{{ Version }}-{{ OS }}", "{{ Version | stripMetadata }}-{{ OS }}"],
            only=[TagPatternFilter.PRIMARY_VARIANT],
        ),
        TagPattern(
            patterns=["{{ Version }}", "{{ Version | stripMetadata }}"],
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
