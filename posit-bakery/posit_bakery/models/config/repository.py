import logging
from typing import List, Set

from pydantic import BaseModel, ConfigDict, field_validator


log = logging.getLogger(__name__)


class ConfigRepository(BaseModel):
    """Configuration for a container image code repository

    Primarily used for labeling purposes

    :param authors: Authors of the repository images
    :param url: URL to the repository (e.g. github.com/rstudio/example)
    :param vendor: Vendor of the images in the repository
    :param maintainer: Maintainer of the images in the repository
    """

    model_config = ConfigDict(frozen=True)

    authors: List[str] = []
    url: str | None = None
    vendor: str | None = "Posit Software, PBC"
    maintainer: str | None = "docker@posit.co"

    @field_validator("authors", mode="after")
    @classmethod
    def vaidate_authors(
        cls,
        authors: Set[str],
    ) -> Set[str]:
        """Ensure the author list is unique

        De-duplicate authors and log a warning if duplicates are found
        """
        unique_authors = set(authors)
        if len(unique_authors) != len(authors):
            log.warning("Duplicate authors found in config.toml")

        return authors
