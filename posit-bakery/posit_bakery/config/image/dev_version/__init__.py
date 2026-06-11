from typing import Annotated, Union

from pydantic import Field

from .base import BaseImageDevelopmentVersion
from .channel import ImageDevelopmentVersionFromProductChannel
from .dependency import ImageDevelopmentVersionFromDependency

DevelopmentVersionTypes = Union[
    ImageDevelopmentVersionFromProductChannel,
    ImageDevelopmentVersionFromDependency,
]
DevelopmentVersionField = Annotated[DevelopmentVersionTypes, Field(discriminator="sourceType")]


__all__ = [
    "BaseImageDevelopmentVersion",
    "ImageDevelopmentVersionFromProductChannel",
    "ImageDevelopmentVersionFromDependency",
    "DevelopmentVersionTypes",
    "DevelopmentVersionField",
]
