from .base import BaseImageDevelopmentVersion
from .channel import ImageDevelopmentVersionFromProductChannel

DevelopmentVersionTypes = ImageDevelopmentVersionFromProductChannel
DevelopmentVersionField = ImageDevelopmentVersionFromProductChannel


__all__ = [
    "BaseImageDevelopmentVersion",
    "ImageDevelopmentVersionFromProductChannel",
    "DevelopmentVersionTypes",
    "DevelopmentVersionField",
]
