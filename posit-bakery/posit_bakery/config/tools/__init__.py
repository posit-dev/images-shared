import logging
from typing import Union, Annotated

from pydantic import Field

from .base import ToolOptions
from .registry import get_tool_options_classes

log = logging.getLogger(__name__)


def _build_tool_field():
    """Build the discriminated union type from all registered tool options classes.

    Returns None if no classes are registered (pre-plugin-discovery).
    """
    classes = get_tool_options_classes()
    if not classes:
        return None
    if len(classes) == 1:
        cls = next(iter(classes.values()))
        return Annotated[cls, Field(discriminator="tool")]
    union = Union[tuple(classes.values())]
    return Annotated[union, Field(discriminator="tool")]


def default_tool_options() -> list[ToolOptions]:
    """Return the default tool options for the bakery configuration.

    Builds defaults from all registered tool options classes.

    :return: A list of default tool options.
    """
    classes = get_tool_options_classes()
    return [cls() for cls in classes.values()]


def rebuild_tool_models() -> None:
    """Rebuild config models that use ToolField after plugins have registered their tool options.

    This must be called after all plugins have registered their tool options classes,
    and before any bakery.yaml parsing occurs.
    """
    from posit_bakery.config.image.image import Image
    from posit_bakery.config.image.variant import ImageVariant
    from posit_bakery.config.image.version import ImageVersion
    from posit_bakery.config.config import BakeryConfigDocument

    tool_field = _build_tool_field()
    if tool_field is None:
        return

    # Update ImageVariant.options field annotation
    ImageVariant.model_fields["options"].annotation = list[tool_field]
    ImageVariant.model_rebuild(force=True)

    # Update Image.options field annotation
    Image.model_fields["options"].annotation = list[tool_field]
    Image.model_rebuild(force=True)

    # Rebuild all parent models up the chain so their cached schemas pick up the changes
    ImageVersion.model_rebuild(force=True)
    BakeryConfigDocument.model_rebuild(force=True)

    log.debug(f"Rebuilt config models with tool options: {list(get_tool_options_classes().keys())}")


# At import time, no plugins are loaded yet. ImageVariant and Image use `list[ToolOptions]`
# as their initial options type (no discriminator). After plugin discovery calls
# rebuild_tool_models(), the field is swapped to a proper discriminated union.
ToolField = ToolOptions


__all__ = [
    "ToolOptions",
    "ToolField",
    "default_tool_options",
    "rebuild_tool_models",
]
