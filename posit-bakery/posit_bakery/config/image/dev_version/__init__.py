from typing import Union, Annotated

from pydantic import Field

from .base import BaseImageDevelopmentVersion
from .env import ImageDevelopmentVersionFromEnv
from .stream import ImageDevelopmentVersionFromProductStream


DevelopmentVersionTypes = Union[ImageDevelopmentVersionFromEnv, ImageDevelopmentVersionFromProductStream]
DevelopmentVersionField = Annotated[DevelopmentVersionTypes, Field(discriminator="sourceType")]


__all__ = [
    "BaseImageDevelopmentVersion",
    "ImageDevelopmentVersionFromEnv",
    "ImageDevelopmentVersionFromProductStream",
    "DevelopmentVersionTypes",
    "DevelopmentVersionField",
]
