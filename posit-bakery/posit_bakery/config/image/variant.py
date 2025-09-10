import logging
from typing import Annotated, Union

from pydantic import Field

from posit_bakery.config.tag import TagPattern
from posit_bakery.config.shared import BakeryYAMLModel, ExtensionField, TagDisplayNameField
from posit_bakery.config.tools import ToolField, default_tool_options, ToolOptions

log = logging.getLogger(__name__)


class ImageVariant(BakeryYAMLModel):
    """Model representing a variant of an image."""

    parent: Annotated[
        Union[BakeryYAMLModel, None] | None, Field(exclude=True, default=None, description="Parent Image object.")
    ]
    name: Annotated[str, Field(description="The full human-readable display name of the image variant.")]
    primary: Annotated[
        bool, Field(default=False, description="Flag to indicate if this is the primary variant of the image.")
    ]
    extension: Annotated[
        ExtensionField,
        Field(
            description="File extension used in the Containerfile filename in the pattern Containerfile.<os>.<variant> "
            "for this variant. Set to an empty string if no extension is needed.",
            examples=["std", "min"],
        ),
    ]
    tagDisplayName: Annotated[
        TagDisplayNameField,
        Field(
            description="The name used in image tags for this variant. This is used to create the tag "
            "in the format <image>:<version>-<os>-<variant>.",
            examples=["std", "min"],
        ),
    ]
    tagPatterns: Annotated[
        list[TagPattern], Field(default_factory=list, description="List of tag patterns for this variant.")
    ]
    options: Annotated[
        list[ToolField],
        Field(default_factory=default_tool_options, description="List of tool options for this variant."),
    ]

    def __hash__(self):
        """Unique hash for an ImageVariant object."""
        return hash((self.name, self.extension, self.tagDisplayName))

    def get_tool_option(self, tool: str, merge_with_parent: bool = True) -> ToolOptions | None:
        """Returns tool options for this image variant.

        By default, the tool option for the variant will be merged with the parent image's tool options if they exist.
        Tool options set to non-defaults in the variant will take precedence over those in the parent.

        :param tool: The name of the tool to get options for.

        :return: The ToolOptions object for the specified tool, or None if not found.
        """
        option = None
        parent_option = None

        for o in self.options:
            if o.tool == tool:
                option = o

        if self.parent is not None and merge_with_parent:
            # Check parent image for tool options first
            parent_option = self.parent.get_tool_option(tool)
            if parent_option is not None and option is None:
                # If the parent has options, use them if the variant does not have its own
                return parent_option

        if option and parent_option:
            # Merge the options if both are found
            return option.update(parent_option)

        return option


def default_image_variants() -> list[ImageVariant]:
    """Return the default image variants for the bakery configuration.

    :return: A list of default image variants.
    """
    return [
        ImageVariant(name="Standard", extension="std", tagDisplayName="std", primary=True),
        ImageVariant(name="Minimal", extension="min", tagDisplayName="min"),
    ]
