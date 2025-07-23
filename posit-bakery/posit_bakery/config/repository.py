import logging
from typing import Annotated

from pydantic import BaseModel, HttpUrl, NameEmail, Field, field_validator


log = logging.getLogger(__name__)


class Repository(BaseModel):
    url: HttpUrl
    vendor: Annotated[str, Field(default="Posit Software, PBC")]
    maintainer: Annotated[NameEmail, Field(default=NameEmail(name="Posit Docker Team", email="docker@posit.co"))]
    authors: Annotated[list[NameEmail], Field(default_factory=list)]

    @field_validator("authors", mode="after")
    @classmethod
    def validate_authors(
        cls,
        authors: list[NameEmail],
    ) -> list[NameEmail]:
        """Ensure the author list is unique

        De-duplicate authors and log a warning if duplicates are found
        """
        unique_authors = set(authors)
        if len(unique_authors) != len(authors):
            warning_message = "Duplicate authors found in .bakery.yaml:\n"
            for unique_author in unique_authors:
                if authors.count(unique_author) > 1:
                    warning_message += f" - {unique_author}\n"

        return list(unique_authors)
