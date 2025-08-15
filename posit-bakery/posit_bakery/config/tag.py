import re
from enum import Enum
from typing import Annotated

from pydantic import Field

from posit_bakery.config.shared import BakeryYAMLModel
from posit_bakery.config.templating.render import jinja2_env


# TODO: Consider how to implement filter logic either as part of TagPattern or as part of images
class TagPatternFilter(str, Enum):
    """Enum representing filters for tag patterns."""

    ALL = "all"  # Matches all image targets.
    LATEST = "latest"  # Matches the image targets at the latest image version.
    PRIMARY_OS = "primaryOS"  # Matches image targets using the primary OS.
    PRIMARY_VARIANT = "primaryVariant"  # Matches image targets of the primary variant.


class TagPattern(BakeryYAMLModel):
    """Model representing a tag pattern for images in the Bakery configuration."""

    patterns: list[
        Annotated[
            str,
            Field(
                pattern=r"^([a-z0-9-_.]|(?P<jinja>\{{2}.+?}{2}))+$",
                description="Tag pattern using Jinja2 syntax.",
                examples=["{{ Version }}-{{ OS }}-{{ Variant }}", "latest"],
            ),
        ]
    ]
    only: Annotated[
        list[TagPatternFilter],
        Field(
            default_factory=lambda: [TagPatternFilter.ALL],
            description="Filters for which image targets should use the tag pattern(s). All filters listed must be "
            "true for the tag pattern to be applied.",
        ),
    ]

    def render(self, **kwargs) -> list[str]:
        """Render the Jinja2 tag patterns with the provided keyword arguments.

        :param kwargs: Key-value pairs to render variables in the Jinja2 tag template.
        """
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
    """Return the default tag patterns for images in the Bakery configuration.

    The default patterns include various combinations of Version, OS, and Variant,
    allowing for flexible tagging of images based on their attributes.

    :return: A list of TagPattern objects representing the default tag patterns.
    """
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
