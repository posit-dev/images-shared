import logging
import math
import os
from urllib.parse import quote

from github import Auth, Github

from posit_bakery.registry_management.ghcr.models import GHCRPackageVersions, GHCRPackageVersion

log = logging.getLogger(__name__)


class GHCRClient:
    ENDPOINTS = {
        "package": "/orgs/{organization}/packages/container/{package}",
        "package_versions": "/orgs/{organization}/packages/container/{package}/versions",
    }

    def __init__(self, organization: str, token: str = os.getenv("GITHUB_TOKEN")):
        self.organization = organization
        auth = Auth.Token(token)
        self.client = Github(auth=auth)

    @classmethod
    def endpoint(cls, endpoint_name: str, **kwargs) -> str:
        endpoint_template = cls.ENDPOINTS.get(endpoint_name)
        if endpoint_template is None:
            raise ValueError(f"Endpoint '{endpoint_name}' not found.")
        return endpoint_template.format(**kwargs)

    def get_package(self, organization: str, package: str) -> dict:
        """Get details on a package."""
        target_url = self.endpoint("package", organization=organization, package=quote(package, safe=""))
        log.debug(f"GET {target_url}")
        _, response = self.client.requester.requestJsonAndCheck(
            "GET",
            target_url,
        )
        return response

    def get_package_versions(self, organization: str, package: str) -> GHCRPackageVersions:
        # Check the number of versions for the package to calculate pagination cycles required.
        response = self.get_package(organization, package)
        version_count = response.get("version_count", 0)
        log.debug(f"Package {package} has {version_count} versions")
        per_page = 100
        page_count = math.ceil(version_count / per_page)

        results = []
        for page in range(1, page_count + 1):
            target_url = self.endpoint("package_versions", organization=organization, package=quote(package, safe=""))
            log.debug(f"GET {target_url} (page {page}/{page_count})")
            _, response = self.client.requester.requestJsonAndCheck(
                "GET",
                target_url,
                parameters={"per_page": 100, "page": page, "state": "active"},
            )
            results.extend(response)

        return GHCRPackageVersions(versions=results)

    def delete_package_version(self, version: GHCRPackageVersion):
        target_endpoint = version.url.removeprefix("https://api.github.com")
        logging.debug(f"DELETE {target_endpoint}")
        self.client.requester.requestJsonAndCheck(
            "DELETE",
            target_endpoint,
        )

    def delete_package_versions(self, versions: GHCRPackageVersions):
        for version in versions.versions:
            self.delete_package_version(version)
