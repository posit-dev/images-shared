import json
import math
import os
from urllib.parse import quote

from github import Auth, Github

from posit_bakery.registry_management.ghcr.models import GHCRPackageVersions, GHCRPackageVersion


class GHCRClient:
    ENDPOINTS = {
        "package": "/orgs/{organization}/packages/container/{package}",
        "package_versions": "/orgs/{organization}/packages/container/{package}/versions",
    }

    def __init__(self, organization: str, token: str = os.getenv("GITHUB_TOKEN")):
        self.organization = organization
        auth = Auth.Token(token)
        self.client = Github(auth=auth)

    def get_package(self, organization: str, package: str) -> dict:
        """Get details on a package."""
        headers, response = self.client.requester.requestJsonAndCheck(
            "GET",
            self.ENDPOINTS["package"].format(organization=organization, package=quote(package)),
        )
        response = json.loads(response)
        return response

    def get_package_versions(self, organization: str, package: str) -> GHCRPackageVersions:
        # Check the number of versions for the package to calculate pagination cycles required.
        response = self.get_package(organization, package)
        version_count = response.get("versionCount", 0)
        per_page = 100
        page_count = math.ceil(version_count / per_page)

        results = []
        for page in range(1, page_count + 1):
            headers, response = self.client.requester.requestJsonAndCheck(
                "GET",
                self.ENDPOINTS["package_versions"].format(organization=organization, package=quote(package)),
                parameters={"per_page": 100, "page": page, "state": "active"},
            )
            response = json.loads(response)
            results.extend(response)

        return GHCRPackageVersions(versions=results)

    def delete_package_version(self, version: GHCRPackageVersion):
        target_endpoint = version.url.removeprefix("https://api.github.com")
        self.client.requester.requestJsonAndCheck(
            "DELETE",
            target_endpoint,
        )

    def delete_package_versions(self, versions: GHCRPackageVersions):
        for version in versions.versions:
            self.delete_package_version(version)
