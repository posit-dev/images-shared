from typing import Annotated, Union

from pydantic import Field

from .base import BaseImageDevelopmentVersion
from .channel import ImageDevelopmentVersionFromProductChannel
from .dependency import ImageDevelopmentVersionFromDependencyPrerelease

DevelopmentVersionTypes = Union[
    ImageDevelopmentVersionFromProductChannel,
    ImageDevelopmentVersionFromDependencyPrerelease,
]
DevelopmentVersionField = Annotated[DevelopmentVersionTypes, Field(discriminator="sourceType")]


__all__ = [
    "BaseImageDevelopmentVersion",
    "ImageDevelopmentVersionFromProductChannel",
    "ImageDevelopmentVersionFromDependencyPrerelease",
    "DevelopmentVersionTypes",
    "DevelopmentVersionField",
]
