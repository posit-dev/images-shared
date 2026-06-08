import logging

from pydantic import field_validator
from pydantic_core.core_schema import ValidationInfo

from posit_bakery.config.image.version_os import ImageVersionOS

log = logging.getLogger(__name__)


class OSValidatorMixin:
    @field_validator("os", mode="after")
    @classmethod
    def check_os_not_empty(cls, os: list[ImageVersionOS], info: ValidationInfo) -> list[ImageVersionOS]:
        """Ensures that the os list is not empty.

        :param os: List of ImageVersionOS objects to check.
        :param info: ValidationInfo containing the data being validated.

        :return: The unmodified list of ImageVersionOS objects.
        """
        if not (info.data.get("name") or info.data.get("namePattern")):
            return os
        if not os:
            log.warning(
                "No OSes defined for the image configuration. At least one OS should be "
                "defined for complete tagging and labeling of images."
            )
        return os

    @field_validator("os", mode="after")
    @classmethod
    def deduplicate_os(cls, os: list[ImageVersionOS], info: ValidationInfo) -> list[ImageVersionOS]:
        """Ensures that the os list is unique and warns on duplicates.

        :param os: List of ImageVersionOS objects to deduplicate.
        :param info: ValidationInfo containing the data being validated.

        :return: A list of unique ImageVersionOS objects.
        """
        unique_oses = set(os)
        for unique_os in unique_oses:
            if os.count(unique_os) > 1:
                log.warning(f"Duplicate OS defined in the image configuration: {unique_os.name}")

        return sorted(list(unique_oses), key=lambda o: o.name)

    @field_validator("os", mode="after")
    @classmethod
    def make_single_os_primary(cls, os: list[ImageVersionOS], info: ValidationInfo) -> list[ImageVersionOS]:
        """Ensures that a single OS entry is automatically marked as primary.

        :param os: List of ImageVersionOS objects to check.
        :param info: ValidationInfo containing the data being validated.

        :return: The list of ImageVersionOS objects with the single OS marked primary.
        """
        # If there's only one OS, mark it as primary by default.
        if len(os) == 1:
            if not os[0].primary:
                log.info(f"Only one OS defined; marking '{os[0].name}' as primary.")
            os[0].primary = True
        return os

    @field_validator("os", mode="after")
    @classmethod
    def max_one_primary_os(cls, os: list[ImageVersionOS], info: ValidationInfo) -> list[ImageVersionOS]:
        """Ensures that at most one OS is marked as primary.

        :param os: List of ImageVersionOS objects to check.
        :param info: ValidationInfo containing the data being validated.

        :return: The list of ImageVersionOS objects with at most one primary OS.

        :raises ValueError: If more than one OS is marked as primary.
        """
        if not (info.data.get("name") or info.data.get("namePattern")):
            return os
        primary_os_count = sum(1 for o in os if o.primary)
        if primary_os_count > 1:
            raise ValueError(
                f"Only one OS can be marked as primary for the image configuration. "
                f"Found {primary_os_count} OSes marked primary."
            )
        elif primary_os_count == 0:
            log.warning(
                "No OS marked as primary for the image configuration. "
                "At least one OS should be marked as primary for complete tagging and labeling of images."
            )
        return os

    # Must run after make_single_os_primary: Pydantic v2 runs field validators in
    # declaration order within the class. Reordering this mixin will silently break
    # the auto-promote invariant for single-OS scratch configs.
    @field_validator("os", mode="after")
    @classmethod
    def error_untaggable_os(cls, os: list[ImageVersionOS], info: ValidationInfo) -> list[ImageVersionOS]:
        """Ensures every non-primary OS has a tagDisplayName.

        A non-primary OS with no tagDisplayName produces images that cannot be
        reached by any tag — they are untaggable.

        :param os: List of ImageVersionOS objects to check.
        :param info: ValidationInfo containing the data being validated.

        :return: The unmodified list of ImageVersionOS objects.

        :raises ValueError: If a non-primary OS has an empty tagDisplayName.
        """
        for o in os:
            if not o.tagDisplayName and not o.primary:
                raise ValueError(
                    f"OS entry '{o.name}' has an empty tagDisplayName but is not the primary OS. "
                    "A non-primary OS with no tagDisplayName produces images that cannot be reached "
                    "by any tag. Set it as primary or remove it from the image configuration."
                )
        return os
