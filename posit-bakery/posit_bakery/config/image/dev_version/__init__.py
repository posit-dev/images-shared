from .base import BaseImageDevelopmentVersion
from .channel import ImageDevelopmentVersionFromProductStream

DevelopmentVersionTypes = ImageDevelopmentVersionFromProductStream
DevelopmentVersionField = ImageDevelopmentVersionFromProductStream


__all__ = [
    "BaseImageDevelopmentVersion",
    "ImageDevelopmentVersionFromProductStream",
    "DevelopmentVersionTypes",
    "DevelopmentVersionField",
]
