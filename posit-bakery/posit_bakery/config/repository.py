import logging
from functools import cached_property
from typing import Annotated, Any

import git
from pydantic import NameEmail, Field, field_validator, computed_field

from posit_bakery.config.shared import BakeryYAMLModel, HttpUrlWithDefaultScheme
from posit_bakery.config.validators import deduplicate_with_warning

log = logging.getLogger(__name__)


class HashableNameEmail(NameEmail):
    """A hashable version of NameEmail for use in sets."""

    def __hash__(self) -> int:
        """Unique hash for a NameEmail object."""
        return hash(str(self))


def parse_name_email_from_dict(name_email_dict: dict[str, str]) -> HashableNameEmail:
    """Parse a dictionary into a NameEmail object.

    :param name_email_dict: A dictionary with 'name' and 'email' keys.
    :return: A HashableNameEmail object.
    """
    if "email" not in name_email_dict:
        raise ValueError(f"Invalid input '{name_email_dict}': 'email' must be provided")
    return HashableNameEmail(**name_email_dict)


class Repository(BakeryYAMLModel):
    """Model representing a project repository in the Bakery configuration."""

    parent: Annotated[
        BakeryYAMLModel, Field(default=None, exclude=True, description="Parent BakeryConfigDocument object.")
    ]
    url: Annotated[HttpUrlWithDefaultScheme, Field(description="URL for the repository. Used in labeling.")]
    vendor: Annotated[str, Field(default="Posit Software, PBC", description="Vendor name for the repository.")]
    maintainer: Annotated[
        HashableNameEmail,
        Field(
            default=HashableNameEmail(name="Posit Docker Team", email="docker@posit.co"),
            description="The primary maintainer of the repository.",
        ),
    ]
    authors: Annotated[
        list[HashableNameEmail], Field(default_factory=list, description="List of authors for the repository.")
    ]

    @computed_field
    @cached_property
    def revision(self) -> str | None:
        """Get the git commit SHA for the repository.

        :return: The git commit SHA if available, otherwise None.
        """
        sha = None
        if self.parent is None:
            return sha
        try:
            repo = git.Repo(self.parent.path, search_parent_directories=True)
            sha = repo.head.object.hexsha
        except Exception as e:
            log.debug(f"Unable to get git commit for labels: {e}")
        return sha

    @field_validator("authors", mode="before")
    @classmethod
    def parse_authors(cls, value: list[Any]) -> list[HashableNameEmail | str]:
        """Parse the authors field into a list of NameEmail objects from dicts or as strings for later validation.

        :param value: The list of authors to parse.

        :return: A list of HashableNameEmail objects parsed from dictionaries and/or strings.
        """
        parsed_authors: list[HashableNameEmail | str] = []
        for v in value:
            if isinstance(v, dict):
                parsed_authors.append(parse_name_email_from_dict(v))
            elif isinstance(v, str):
                parsed_authors.append(v)
            else:
                raise ValueError(
                    f"Invalid input for author '{v}': must be a string or dict with 'name' and 'email' keys"
                )
        return parsed_authors

    @field_validator("maintainer", mode="before")
    @classmethod
    def parse_maintainer(cls, value: Any) -> HashableNameEmail | str:
        """Parse the maintainer field into a NameEmail object or return as is if already a str for later validation.

        :param value: The maintainer to parse.

        :return: A HashableNameEmail object parsed from a dictionary or the string value if already a string.
        """
        if isinstance(value, dict):
            return parse_name_email_from_dict(value)
        elif isinstance(value, str):
            return value
        else:
            raise ValueError(
                f"Invalid input for maintainer '{value}': must be a string or dict with 'name' and 'email' keys"
            )

    @field_validator("authors", mode="after")
    @classmethod
    def deduplicate_authors(
        cls,
        authors: list[NameEmail],
    ) -> list[NameEmail]:
        """De-duplicate and sort authors. Logs a warning if duplicates are found.

        :param authors: The list of authors to deduplicate.

        :return: A list of unique authors.
        """
        return deduplicate_with_warning(
            authors,
            key=lambda x: str(x).lower(),
            warn_message_func=lambda a: f"Duplicate authors found in bakery.yaml: {a}",
        )
