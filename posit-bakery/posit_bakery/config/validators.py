"""Shared validation utilities and mixins for Pydantic models.

This module provides reusable validation utilities and mixin classes for common
validation patterns across the bakery configuration models.
"""

import logging
from typing import Callable, Hashable, Self, TypeVar

from pydantic import field_validator, model_validator
from pydantic_core.core_schema import ValidationInfo

from posit_bakery.config.registry import BaseRegistry, Registry
from posit_bakery.config.shared import BakeryYAMLModel

log = logging.getLogger(__name__)

T = TypeVar("T")


def deduplicate_with_warning(
    items: list[T],
    key: Callable[[T], str],
    warn_message_func: Callable[[T], str] | None = None,
) -> list[T]:
    """Deduplicate a list, warn on duplicates, and sort by key.

    Use this for soft validation where duplicates are allowed but discouraged.
    Examples: registry lists, author lists.

    Args:
        items: List to deduplicate
        key: Function to extract sort key from item
        warn_message_func: Optional function that takes duplicate item and returns warning message.
                          If None, no warning is logged.

    Returns:
        Deduplicated and sorted list (original list is not modified)
    """
    unique_items = set(items)
    if warn_message_func is not None:
        for unique_item in unique_items:
            if items.count(unique_item) > 1:
                log.warning(warn_message_func(unique_item))
    return sorted(list(unique_items), key=key)


def check_duplicates_or_raise(
    items: list[T],
    key_func: Callable[[T], Hashable],
    error_message_func: Callable[[list[Hashable]], str],
) -> list[T]:
    """Check for duplicates and raise ValueError if found.

    Use this for strict validation where duplicates are not allowed.
    Examples: version names, variant names, dependency constraints.

    Args:
        items: List to check
        key_func: Function to extract hashable key from item (e.g., lambda v: v.name)
        error_message_func: Function that takes list of *duplicate keys* (not items) and returns
                           error message. Keys are the values returned by key_func for items
                           that appeared more than once.
                           Example: lambda dupes: f"Duplicate versions: {', '.join(dupes)}"

    Returns:
        Original list unchanged if no duplicates

    Raises:
        ValueError: If duplicates are found, with message from error_message_func

    Example:
        check_duplicates_or_raise(
            versions,
            key_func=lambda v: v.name,
            error_message_func=lambda dupes: f"Duplicate version names: {', '.join(dupes)}"
        )
    """
    seen: set[Hashable] = set()
    duplicates: list[Hashable] = []
    for item in items:
        item_key = key_func(item)
        if item_key in seen:
            if item_key not in duplicates:
                duplicates.append(item_key)
        seen.add(item_key)

    if duplicates:
        raise ValueError(error_message_func(duplicates))

    return items


class RegistryValidationMixin:
    """Mixin for models with extraRegistries/overrideRegistries fields.

    This mixin provides:
    - Registry deduplication with warnings
    - Mutual exclusivity validation between extraRegistries and overrideRegistries

    Models using this mixin must have `extraRegistries` and `overrideRegistries` fields.
    Override `_get_registry_context()` to customize the context string in messages.

    For models without a name/namePattern field (e.g., BaseImageDevelopmentVersion),
    override `_context_is_optional()` to return True to enable warnings without context.
    """

    @classmethod
    def _get_registry_context(cls, info: ValidationInfo | None) -> str | None:
        """Return context string for messages. Default uses 'name' field from info.data.

        Override in subclasses that use different identifier fields (e.g., 'namePattern').
        Returns None if info is None or the field is not present.
        """
        if info is None:
            return None
        return info.data.get("name") or info.data.get("namePattern") or None

    @classmethod
    def _get_registry_context_type(cls) -> str:
        """Return the type name for messages (e.g., 'image', 'image version').

        Default returns an empty string for backwards compatibility with existing messages.
        Override in subclasses for more specific messages.
        """
        return ""

    @classmethod
    def _context_is_optional(cls) -> bool:
        """Return True if the model doesn't have a name/namePattern field.

        Override to return True in models like BaseImageDevelopmentVersion that
        don't have a context identifier. When True, warnings will use context_type
        only and won't be suppressed due to missing context.
        """
        return False

    @field_validator("extraRegistries", "overrideRegistries", mode="after")
    @classmethod
    def deduplicate_registries(
        cls, registries: list[Registry | BaseRegistry], info: ValidationInfo
    ) -> list[Registry | BaseRegistry]:
        """Ensures that the registries list is unique and warns on duplicates.

        :param registries: List of registries to deduplicate.
        :param info: ValidationInfo containing the data being validated.

        :return: A list of unique registries.
        """
        context = cls._get_registry_context(info)
        context_type = cls._get_registry_context_type()

        def warn_message(registry: Registry | BaseRegistry) -> str:
            if context:
                if context_type:
                    return f"Duplicate registry defined in config for {context_type} '{context}': {registry.base_url}"
                return f"Duplicate registry defined in config for '{context}': {registry.base_url}"
            if context_type:
                return f"Duplicate registry defined in config for {context_type}: {registry.base_url}"
            return f"Duplicate registry defined in config: {registry.base_url}"

        # Only warn if we have context or context is optional (avoid partial validation warnings)
        warn_func = warn_message if (context or cls._context_is_optional()) else None
        return deduplicate_with_warning(registries, key=lambda r: r.base_url, warn_message_func=warn_func)

    @model_validator(mode="after")
    def validate_registry_mutual_exclusivity(self) -> Self:
        """Ensures that only one of extraRegistries or overrideRegistries is defined.

        :raises ValueError: If both extraRegistries and overrideRegistries are defined.
        """
        if self.extraRegistries and self.overrideRegistries:
            # Get context from the model instance
            context = getattr(self, "name", None) or getattr(self, "namePattern", None)
            context_type = self._get_registry_context_type()
            if context:
                if context_type:
                    raise ValueError(
                        f"Only one of 'extraRegistries' or 'overrideRegistries' can be defined for "
                        f"{context_type} '{context}'."
                    )
                raise ValueError(
                    f"Only one of 'extraRegistries' or 'overrideRegistries' can be defined for '{context}'."
                )
            if context_type:
                raise ValueError(
                    f"Only one of 'extraRegistries' or 'overrideRegistries' can be defined for {context_type}."
                )
            raise ValueError("Only one of 'extraRegistries' or 'overrideRegistries' can be defined.")
        return self


class OSValidationMixin:
    """Mixin for models with an 'os' field of type list[ImageVersionOS].

    This mixin provides:
    - Empty OS list warning
    - OS deduplication with warnings
    - Auto-marking single OS as primary
    - Validation that at most one OS is primary

    Models using this mixin must have an `os` field.
    Override `_get_os_context()` and `_get_os_context_type()` to customize messages.

    For models without a name/namePattern field (e.g., BaseImageDevelopmentVersion),
    override `_context_is_optional()` to return True to enable warnings without context.
    """

    @classmethod
    def _get_os_context(cls, info: ValidationInfo | None) -> str | None:
        """Return context string for messages. Default uses 'name' field from info.data.

        Override in subclasses that use different identifier fields (e.g., 'namePattern').
        Returns None if info is None or the field is not present.
        """
        if info is None:
            return None
        return info.data.get("name") or info.data.get("namePattern") or None

    @classmethod
    def _get_os_context_type(cls) -> str:
        """Return the type name for messages (e.g., 'image version', 'matrix').

        Default returns 'image version'. Override in Matrix, DevVersion, etc.
        """
        return "image version"

    @classmethod
    def _context_is_optional(cls) -> bool:
        """Return True if the model doesn't have a name/namePattern field.

        Override to return True in models like BaseImageDevelopmentVersion that
        don't have a context identifier. When True, warnings will use context_type
        only and won't be suppressed due to missing context.
        """
        return False

    @classmethod
    def _check_os_not_empty(cls, os: list, info: ValidationInfo | None) -> list:
        """Warn if OS list is empty."""
        context = cls._get_os_context(info)
        context_type = cls._get_os_context_type()

        if not os:
            if context:
                log.warning(
                    f"No OSes defined for {context_type} '{context}'. At least one OS should be defined for "
                    f"complete tagging and labeling of images."
                )
            elif cls._context_is_optional():
                # Model doesn't have a name field, use shorter message
                log.warning(
                    f"No OSes defined for {context_type}. At least one OS should be "
                    "defined for complete tagging and labeling of images."
                )
            # If context is None and not optional, skip warning (partial validation)
        return os

    @classmethod
    def _deduplicate_os(cls, os: list, info: ValidationInfo | None) -> list:
        """Deduplicate OS list with warnings."""
        context = cls._get_os_context(info)
        context_type = cls._get_os_context_type()

        def warn_message(os_item) -> str:
            if context:
                return f"Duplicate OS defined in config for {context_type} '{context}': {os_item.name}"
            return f"Duplicate OS defined in config for {context_type}: {os_item.name}"

        # Only warn if we have context or context is optional
        warn_func = warn_message if (context or cls._context_is_optional()) else None
        return deduplicate_with_warning(os, key=lambda o: o.name, warn_message_func=warn_func)

    @classmethod
    def _make_single_os_primary(cls, os: list, info: ValidationInfo | None) -> list:
        """Auto-mark single OS as primary."""
        context = cls._get_os_context(info)
        context_type = cls._get_os_context_type()

        # If there's only one OS, mark it as primary by default.
        if len(os) == 1:
            if not os[0].primary:
                if context:
                    log.info(
                        f"Only one OS, {os[0].name}, defined for {context_type} {context}. Marking it as primary OS."
                    )
                # For no-context models, silently mark as primary
                os[0].primary = True
        return os

    @classmethod
    def _max_one_primary_os(cls, os: list, info: ValidationInfo | None) -> list:
        """Ensure at most one OS is marked primary."""
        context = cls._get_os_context(info)
        context_type = cls._get_os_context_type()

        primary_os_count = sum(1 for o in os if o.primary)
        if primary_os_count > 1:
            if context:
                raise ValueError(
                    f"Only one OS can be marked as primary for {context_type} '{context}'. "
                    f"Found {primary_os_count} OSes marked primary."
                )
            raise ValueError(
                f"Only one OS can be marked as primary for {context_type}. "
                f"Found {primary_os_count} OSes marked primary."
            )
        elif primary_os_count == 0:
            if context:
                log.warning(
                    f"No OS marked as primary for {context_type} '{context}'. "
                    "At least one OS should be marked as primary for complete tagging and labeling of images."
                )
            elif cls._context_is_optional():
                # Model doesn't have a name field, use shorter message
                log.warning(
                    f"No OS marked as primary for {context_type}. "
                    "At least one OS should be marked as primary for complete tagging and labeling of images."
                )
            # If context is None and not optional, skip warning (partial validation)
        return os

    @field_validator("os", mode="after")
    @classmethod
    def validate_os(cls, os: list, info: ValidationInfo) -> list:
        """Combined OS validator that runs all checks in guaranteed order.

        This single validator calls private helpers in sequence to ensure
        deterministic execution order regardless of MRO or Pydantic internals.
        """
        os = cls._check_os_not_empty(os, info)
        os = cls._deduplicate_os(os, info)
        os = cls._make_single_os_primary(os, info)
        os = cls._max_one_primary_os(os, info)
        return os
