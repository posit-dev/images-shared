import json
import math
import os
from urllib.parse import quote

from github import Auth, Github, GithubException

from posit_bakery.registry_management.ghcr.models import GHCRPackageVersions, GHCRPackageVersion


def github_client(token: str = os.getenv("GITHUB_TOKEN")) -> Github:
    """Authenticate with Github using PyGithub and return a Github client."""
    auth = Auth.Token(token)
    return Github(auth=auth)


def get_package(
    client: Github,
    organization: str,
    package: str,
) -> dict:
    """Get details on a package."""
    headers, response = client.requester.requestJsonAndCheck(
        "GET",
        f"/orgs/{organization}/packages/container/{quote(package)}",
    )
    response = json.loads(response)
    return response


def get_package_versions(
    client: Github,
    organization: str,
    package: str,
) -> GHCRPackageVersions:
    # Check the number of versions for the package to calculate pagination cycles required.
    response = get_package(client, organization, package)
    version_count = response.get("versionCount", 0)
    per_page = 100
    page_count = math.ceil(version_count / per_page)

    results = []
    for page in range(1, page_count + 1):
        headers, response = client.requester.requestJsonAndCheck(
            "GET",
            f"/orgs/{organization}/packages/container/{quote(package)}/versions",
            parameters={"per_page": 100, "page": page, "state": "active"},
        )
        response = json.loads(response)
        results.extend(response)

    return GHCRPackageVersions(versions=results)


def delete_package_version(
    client: Github,
    version: GHCRPackageVersion,
):
    target_endpoint = version.url.removeprefix("https://api.github.com")
    client.requester.requestJsonAndCheck(
        "DELETE",
        target_endpoint,
    )


def delete_package_versions(
    client: Github,
    versions: GHCRPackageVersions,
):
    for version in versions.versions:
        delete_package_version(client, version)
