from datetime import datetime, timedelta, UTC

from pydantic import BaseModel


class GHCRPackageVersionContainerMetadata(BaseModel):
    """Represents container metadata for a GitHub Container Registry package version."""

    tags: list[str]


class GHCRPackageVersionMetadata(BaseModel):
    """Represents metadata for a GitHub Container Registry package version."""

    package_type: str
    container: GHCRPackageVersionContainerMetadata


class GHCRPackageVersion(BaseModel):
    """Represents a GitHub Container Registry package version."""

    id: int
    name: str
    url: str
    package_html_url: str
    created_at: datetime
    updated_at: datetime
    html_url: str
    metadata: GHCRPackageVersionMetadata


class GHCRPackageVersions(BaseModel):
    """Represents a list of GitHub Container Registry package versions."""

    versions: list[GHCRPackageVersion]

    def filter_older_than(self, td: timedelta = timedelta(weeks=2)):
        now = datetime.now(UTC)
        limit = now - td

        filtered_versions = []
        for version in self.versions:
            if limit > version.updated_at:
                filtered_versions.append(version)

        return GHCRPackageVersions(versions=filtered_versions)

    def filter_untagged(self):
        filtered_versions = []
        for version in self.versions:
            if len(version.metadata.container.tags) == 0:
                filtered_versions.append(version)

        return GHCRPackageVersions(versions=filtered_versions)
