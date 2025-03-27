from collections import OrderedDict
from typing import Annotated

import requests
from pydantic import BaseModel, HttpUrl, Field

from posit_bakery.models.manifest import BuildOS, OSFamilyEnum
from posit_bakery.web import resolvers
from posit_bakery.web.resolvers import AbstractResolver, StringMapPathResolver
from posit_bakery.web.version.product.const import SEMVER_REGEX_PATTERN, ProductEnum, ReleaseStreamEnum


class ReleaseStreamResult(BaseModel):
    """Represents a resulting artifact found in a release stream. This provides an easy validation for data we get."""

    version: Annotated[str, Field(pattern=SEMVER_REGEX_PATTERN)]
    download_url: HttpUrl


class ReleaseStreamPath:
    """Represents a path to a release stream and a map of resolvers to extract data from the fetched data."""

    def __init__(self, stream_url: str, resolver_map: dict[str, AbstractResolver | str]):
        self.stream_url = stream_url
        self.resolver_map = resolver_map

    def get(self, metadata: dict) -> ReleaseStreamResult:
        """Fetches data from the stream URL and resolves the data using the given resolvers."""
        response = requests.get(self.stream_url)
        response.raise_for_status()
        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            data = response.text

        result = {k: "" for k in self.resolver_map.keys()}
        for key, resolver in self.resolver_map.items():
            if isinstance(resolver, str):
                result[key] = resolver.format(**metadata, **result)
            else:
                result[key] = resolver.resolve(data)

        return ReleaseStreamResult(**result)


# This map connects products to their respective release streams. Each release stream has a ReleaseStreamPath object
# that defines one URL to fetch data from and a map of resolvers that can be used to extract a specified property
# from the fetched data as it is expected to be formatted.
PRODUCT_RELEASE_STREAM_URL_MAP = {
    ProductEnum.CONNECT: {
        ReleaseStreamEnum.RELEASE: ReleaseStreamPath(
            "https://posit.co/wp-content/uploads/downloads.json",
            {
                "version": resolvers.StringMapPathResolver(["connect", "installer", "{download_json_os}", "version"]),
                "download_url": resolvers.StringMapPathResolver(
                    ["connect", "installer", "{parse_download_json_os_identifier(os)}", "url"]
                ),
            },
        ),
        ReleaseStreamEnum.DAILY: ReleaseStreamPath(
            "https://cdn.posit.co/connect/latest-packages.json",
            {
                "version": resolvers.ChainedResolver(
                    [
                        resolvers.StringMapPathResolver(["packages"]),
                        resolvers.ArrayPropertyResolver(
                            "platform", "{os.name.lower()}{os.major_version}/{arch_identifier}"
                        ),
                        resolvers.StringMapPathResolver(["version"]),
                    ]
                ),
                "download_url": resolvers.ChainedResolver(
                    [
                        resolvers.StringMapPathResolver(["packages"]),
                        resolvers.ArrayPropertyResolver(
                            "platform", "{os.name.lower()}{os.major_version}/{arch_identifier}"
                        ),
                        resolvers.StringMapPathResolver(["url"]),
                    ]
                ),
            },
        ),
    },
    ProductEnum.PACKAGE_MANAGER: {
        ReleaseStreamEnum.RELEASE: ReleaseStreamPath(
            "https://posit.co/wp-content/uploads/downloads.json",
            {
                "version": resolvers.StringMapPathResolver(["rspm", "installer", "{download_json_os}", "version"]),
                "download_url": resolvers.StringMapPathResolver(["rspm", "installer", "{download_json_os}", "url"]),
            },
        ),
        ReleaseStreamEnum.PREVIEW: ReleaseStreamPath(
            "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm-rc-latest.txt",
            # This is intentionally stored as an OrderedDict to ensure version is resolved first so it can be passed
            # to the download_url resolver.
            OrderedDict(
                [
                    ("version", resolvers.TextResolver()),
                    (
                        "download_url",
                        "https://cdn.posit.co/package-manager/{os}/{arch_identifier}/rstudio-pm_{version}_amd64.deb",
                    ),
                ]
            ),
        ),
        ReleaseStreamEnum.DAILY: ReleaseStreamPath(
            "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm-main-latest.txt",
            OrderedDict(
                [
                    ("version", resolvers.TextResolver()),
                    (
                        "download_url",
                        "https://cdn.posit.co/package-manager/{os}/{arch_identifier}/rstudio-pm_{version}_amd64.deb",
                    ),
                ]
            ),
        ),
    },
    ProductEnum.WORKBENCH: {
        ReleaseStreamEnum.RELEASE: ReleaseStreamPath(
            "https://posit.co/wp-content/uploads/downloads.json",
            {
                "version": resolvers.StringMapPathResolver(
                    ["rstudio", "pro", "stable", "server", "installer", "{download_json_os}", "version"]
                ),
                "download_url": resolvers.StringMapPathResolver(
                    ["rstudio", "pro", "stable", "server", "installer", "{download_json_os}", "url"]
                ),
            },
        ),
        ReleaseStreamEnum.PREVIEW: ReleaseStreamPath(
            "https://www.rstudio.com/products/rstudio/download/preview/",
            {
                "version": resolvers.StringMapPathResolver(
                    ["rstudio", "pro", "preview", "server", "installer", "{download_json_os}", "version"]
                ),
                "download_url": resolvers.StringMapPathResolver(
                    ["rstudio", "pro", "preview", "server", "installer", "{download_json_os}", "url"]
                ),
            },
        ),
        ReleaseStreamEnum.DAILY: ReleaseStreamPath(
            "https://dailies.posit.co/rstudio/latest/index.json",
            {
                "version": resolvers.StringMapPathResolver(
                    ["products", "workbench", "platforms", "{download_json_os}-{arch_identifier}", "version"]
                ),
                "download_url": resolvers.StringMapPathResolver(
                    ["products", "workbench", "platforms", "{download_json_os}-{arch_identifier}", "link"]
                ),
            },
        ),
    },
    ProductEnum.WORKBENCH_SESSION: {
        ReleaseStreamEnum.RELEASE: ReleaseStreamPath(
            "https://posit.co/wp-content/uploads/downloads.json",
            {
                "version": resolvers.StringMapPathResolver(
                    ["rstudio", "pro", "stable", "session", "installer", "{download_json_os}", "version"]
                ),
                "download_url": resolvers.StringMapPathResolver(
                    ["rstudio", "pro", "stable", "session", "installer", "{download_json_os}", "url"]
                ),
            },
        ),
        ReleaseStreamEnum.PREVIEW: ReleaseStreamPath(
            "https://www.rstudio.com/products/rstudio/download/preview/",
            {
                "version": resolvers.StringMapPathResolver(
                    ["rstudio", "pro", "preview", "session", "installer", "{download_json_os}", "version"]
                ),
                "download_url": resolvers.StringMapPathResolver(
                    ["rstudio", "pro", "preview", "session", "installer", "{download_json_os}", "url"]
                ),
            },
        ),
        ReleaseStreamEnum.DAILY: ReleaseStreamPath(
            "https://dailies.posit.co/rstudio/latest/index.json",
            {
                "version": resolvers.StringMapPathResolver(
                    ["products", "session", "platforms", "{download_json_os}-{arch_identifier}", "version"]
                ),
                "download_url": resolvers.StringMapPathResolver(
                    ["products", "session", "platforms", "{download_json_os}-{arch_identifier}", "link"]
                ),
            },
        ),
    },
}


def _parse_download_json_os_identifier(_os: BuildOS, product: ProductEnum) -> str:
    """We have little standardization on how OSes are named product to product. This function will attempt to
    resolve to the correct one based on the given product and OS.
    """
    debian_to_ubuntu_codename = {
        "bookworm": "noble",
        "bullseye": "jammy",
        "buster": "focal",
    }
    if _os.family == OSFamilyEnum.DEBIAN_LIKE:
        if _os.name.lower() == "ubuntu":
            return _os.codename
        elif _os.name.lower() == "debian":
            return debian_to_ubuntu_codename.get(_os.codename)
    elif _os.family == OSFamilyEnum.SUSE_LIKE:
        return "opensuse" + _os.version
    elif _os.family == OSFamilyEnum.REDHAT_LIKE:
        if product == ProductEnum.CONNECT:
            if _os.version == "8":
                return "redhat8"
            elif _os.version == "9":
                return "rhel9"
        elif product == ProductEnum.PACKAGE_MANAGER:
            if _os.version == "7":
                return "rhel7_64"
            elif _os.version == "8":
                return "fedora28"
            elif _os.version == "9":
                return "rhel9"
        elif product == ProductEnum.WORKBENCH or product == ProductEnum.WORKBENCH_SESSION:
            return "rhel" + _os.version

    # Return multi if we can't resolve to a specific OS, this does work for some products
    return "multi"


def _make_resolver_metadata(os: BuildOS, product: ProductEnum):
    """Generates a set of metadata used in string formatting with the given OS and Product."""
    arch_identifier = "amd64"
    if os.family == OSFamilyEnum.REDHAT_LIKE:
        arch_identifier = "x86_64"

    return {
        "os": os,
        "download_json_os": _parse_download_json_os_identifier(os, product),
        "arch_identifier": arch_identifier,
    }


def get_product_artifact_by_stream(product: ProductEnum, stream: ReleaseStreamEnum, os: BuildOS) -> ReleaseStreamResult:
    """Fetches the version and download URL for a given product, release stream, and OS."""
    metadata = _make_resolver_metadata(os, product)
    return PRODUCT_RELEASE_STREAM_URL_MAP[product][stream].get(metadata)
