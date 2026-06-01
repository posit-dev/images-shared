from .base import BaseImageDevelopmentVersion
from .stream import ImageDevelopmentVersionFromProductStream

DevelopmentVersionTypes = ImageDevelopmentVersionFromProductStream
DevelopmentVersionField = ImageDevelopmentVersionFromProductStream


__all__ = [
    "BaseImageDevelopmentVersion",
    "ImageDevelopmentVersionFromProductStream",
    "DevelopmentVersionTypes",
    "DevelopmentVersionField",
]
