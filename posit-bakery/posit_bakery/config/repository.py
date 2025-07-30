import logging
from typing import Annotated, Any

from pydantic import HttpUrl, NameEmail, Field, field_validator, AnyUrl

from posit_bakery.config.shared import BakeryYAMLModel

log = logging.getLogger(__name__)


class HashableNameEmail(NameEmail):
    """A hashable version of NameEmail for use in sets"""

    def __hash__(self) -> int:
        """Unique hash for a NameEmail object"""
        return hash(str(self))


def parse_name_email_from_dict(name_email_dict: dict) -> HashableNameEmail:
    """Parse a dictionary into a NameEmail object"""
    if "email" not in name_email_dict:
        raise ValueError(f"Invalid input '{name_email_dict}': 'email' must be provided")
    return HashableNameEmail(**name_email_dict)


class Repository(BakeryYAMLModel):
    url: HttpUrl
    vendor: Annotated[str, Field(default="Posit Software, PBC")]
    maintainer: Annotated[
        HashableNameEmail, Field(default=NameEmail(name="Posit Docker Team", email="docker@posit.co"))
    ]
    authors: Annotated[list[HashableNameEmail], Field(default_factory=list)]

    @field_validator("url", mode="before")
    @classmethod
    def default_https_url_scheme(cls, value: AnyUrl) -> HttpUrl:
        """Prepend 'https://' to the URL if it does not already start with it"""
        if isinstance(value, str):
            if not value.startswith("https://"):
                value = f"https://{value}"
        return value

    @field_validator("authors", mode="before")
    @classmethod
    def parse_authors(cls, value: list[Any]) -> list[HashableNameEmail | str]:
        """Parse the authors field into a list of NameEmail objects from dicts or as strings for later validation"""
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
        """Parse the maintainer field into a NameEmail object or return as is if already a str for later validation"""
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
        """Ensure the author list is unique

        De-duplicate authors and log a warning if duplicates are found
        """
        unique_authors = set(authors)
        warning_message = ""
        if len(unique_authors) != len(authors):
            warning_message = "Duplicate authors found in .bakery.yaml:\n"
            for unique_author in unique_authors:
                if authors.count(unique_author) > 1:
                    warning_message += f" - {unique_author}\n"
        if warning_message:
            log.warning(warning_message.strip())

        return list(unique_authors)
