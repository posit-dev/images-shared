import logging
from typing import List

from pydantic import BaseModel, field_validator, model_validator

from posit_bakery.models.config.registry import ConfigRegistry
from posit_bakery.models.config.repository import ConfigRepository


log = logging.getLogger("rich")


class ConfigDocument(BaseModel):
    """Document model for a config.toml file

    :param repository: Repository information for labeling purposes
    :param registries: One or more image registries to use for tagging and pushing images

    Example:

        [repository]
        url = "github.com/posit-dev/images-shared"
        vendor = "Posit Software, PBC"
        maintainer = "docker@posit.co"
        authors = [
            "Author 1 <author1@posit.co>",
            "Author 2 <author2@posit.co>",
        ]

        [[registries]]
        host = "docker.io"
        namespace = "posit"

        [[registries]]
        host = "ghcr.io"
        namespace = "posit-dev"
    """

    repository: ConfigRepository = None
    registries: List[ConfigRegistry]

    @model_validator(mode="after")
    def validate_repository(self) -> ConfigRepository:
        """Log a warning if repository is undefined

        Repository information is used for labeling purposes
        """
        if self.repository is None:
            log.warning("Repository not found in config.toml")

        return self

    @field_validator("registries", mode="after")
    @classmethod
    def validate_registries(
        cls,
        registries: List[ConfigRegistry],
    ) -> List[ConfigRegistry]:
        """Ensure that the registry list is unique and sorted

        De-duplicate registries and log a warning if duplicates are found
        """
        unique_registries = set(registries)
        if len(unique_registries) != len(registries):
            log.warning("Duplicate registries found in config.toml")

        return sorted(unique_registries, key=lambda x: x.base_url)
