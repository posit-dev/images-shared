"""Shared mixins for image configuration models.

This module provides reusable mixins that extract common patterns from
ImageVersion, ImageMatrix, and BaseImageDevelopmentVersion.
"""

from copy import deepcopy
from pathlib import Path
from typing import Self

from pydantic import model_validator

from posit_bakery.config.image.build_os import DEFAULT_PLATFORMS, TargetPlatform
from posit_bakery.config.registry import BaseRegistry, Registry


class SubpathMixin:
    """Mixin for models that derive their path from parent.path + subpath.

    Models using this mixin must have:
    - `parent` attribute with a `path` property
    - `subpath` attribute
    """

    @property
    def path(self) -> Path | None:
        """Returns the path to the model's directory.

        :raises ValueError: If the parent does not have a valid path.
        """
        if self.parent is None or self.parent.path is None:
            raise ValueError("Parent image must resolve a valid path.")
        return Path(self.parent.path) / Path(self.subpath)


class SupportedPlatformsMixin:
    """Mixin for models that compute supported platforms from their OS list.

    Models using this mixin must have:
    - `os` attribute (list of objects with `platforms` attribute)
    """

    @property
    def supported_platforms(self) -> list[TargetPlatform]:
        """Returns a list of supported target platforms.

        :return: A list of TargetPlatform objects supported by this model.
        """
        if not self.os:
            return DEFAULT_PLATFORMS

        platforms = []
        for version_os in self.os:
            for platform in version_os.platforms:
                if platform not in platforms:
                    platforms.append(platform)
        return platforms


class AllRegistriesMixin:
    """Mixin for models that merge registries from parent.

    Models using this mixin must have:
    - `parent` attribute (optional, with `all_registries` property)
    - `extraRegistries` attribute
    - `overrideRegistries` attribute
    """

    @property
    def all_registries(self) -> list[Registry | BaseRegistry]:
        """Returns the merged registries for this model.

        :return: A list of registries that includes the overrideRegistries or the
            model's extraRegistries merged with any registries from the parent.
        """
        # If overrideRegistries are set, return those directly.
        if self.overrideRegistries:
            return deepcopy(self.overrideRegistries)

        # Otherwise, merge the registries from this model and its parent.
        all_registries = deepcopy(self.extraRegistries)
        if self.parent is not None:
            for registry in self.parent.all_registries:
                if registry not in all_registries:
                    all_registries.append(registry)

        return all_registries


class OSParentageMixin:
    """Mixin for models that need to set parent references on their OS objects.

    Models using this mixin must have:
    - `os` attribute (list of objects with settable `parent` attribute)

    Note: This mixin provides a model_validator. When using multiple validators,
    be aware of Pydantic's validator execution order.
    """

    @model_validator(mode="after")
    def resolve_parentage(self) -> Self:
        """Sets the parent for all OSes in this model."""
        for version_os in self.os:
            version_os.parent = self
        return self
