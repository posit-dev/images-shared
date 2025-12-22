from collections import OrderedDict
from typing import Annotated

import requests
from pydantic import BaseModel, AnyUrl, Field

from posit_bakery.config.image.build_os import BuildOS
from posit_bakery.config.image.posit_product import resolvers
from posit_bakery.config.image.posit_product.const import (
    CALVER_REGEX_PATTERN,
    ProductEnum,
    ReleaseStreamEnum,
    WORKBENCH_DAILY_URL,
    PACKAGE_MANAGER_DAILY_URL,
    PACKAGE_MANAGER_PREVIEW_URL,
    CONNECT_DAILY_URL,
    DOWNLOADS_JSON_URL,
)
from posit_bakery.config.shared import OSFamilyEnum
from posit_bakery.util import cached_session


class ReleaseStreamResult(BaseModel):
    """Represents a resulting artifact found in a release stream. This provides an easy validation for data we get."""

    version: Annotated[str, Field(pattern=CALVER_REGEX_PATTERN)]
    download_url: str | HttpUrl


class ReleaseStreamPath:
    """Represents a path to a release stream and a map of resolvers to extract data from the fetched data."""

    def __init__(self, stream_url: str, resolver_map: dict[str, resolvers.AbstractResolver | str]):
        self.stream_url = stream_url
        self.resolver_map = resolver_map

    def get(self, metadata: dict) -> ReleaseStreamResult:
        """Fetches data from the stream URL and resolves the data using the given resolvers."""
        session = cached_session()
        response = session.get(self.stream_url)
        response.raise_for_status()
        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            data = response.text

        result = {k: "" for k in self.resolver_map.keys()}
        for key, resolver in self.resolver_map.items():
            if isinstance(resolver, str):
                result[key] = resolver.format(**metadata, **result)
            elif isinstance(resolver, resolvers.AbstractResolver):
                resolver.set_metadata(metadata)
                result[key] = resolver.resolve(data)

        return ReleaseStreamResult(**result)


# This map connects products to their respective release streams. Each release stream has a ReleaseStreamPath object
# that defines one URL to fetch data from and a map of resolvers that can be used to extract a specified property
# from the fetched data as it is expected to be formatted.
product_release_stream_url_map = {
    ProductEnum.CONNECT: {
        ReleaseStreamEnum.RELEASE: ReleaseStreamPath(
            DOWNLOADS_JSON_URL,
            {
                "version": resolvers.StringMapPathResolver(["connect", "installer", "{download_json_os}", "version"]),
                "download_url": resolvers.StringMapPathResolver(["connect", "installer", "{download_json_os}", "url"]),
            },
        ),
        ReleaseStreamEnum.DAILY: ReleaseStreamPath(
            CONNECT_DAILY_URL,
            {
                "version": resolvers.ChainedResolver(
                    [
                        resolvers.StringMapPathResolver(["packages"]),
                        resolvers.ArrayPropertyResolver("platform", "{connect_daily_os_name}/{arch_identifier}"),
                        resolvers.StringMapPathResolver(["version"]),
                    ]
                ),
                "download_url": resolvers.ChainedResolver(
                    [
                        resolvers.StringMapPathResolver(["packages"]),
                        resolvers.ArrayPropertyResolver("platform", "{connect_daily_os_name}/{arch_identifier}"),
                        resolvers.StringMapPathResolver(["url"]),
                    ]
                ),
            },
        ),
    },
    ProductEnum.PACKAGE_MANAGER: {
        ReleaseStreamEnum.RELEASE: ReleaseStreamPath(
            DOWNLOADS_JSON_URL,
            {
                "version": resolvers.StringMapPathResolver(["rspm", "installer", "{download_json_os}", "version"]),
                "download_url": resolvers.StringMapPathResolver(["rspm", "installer", "{download_json_os}", "url"]),
            },
        ),
        ReleaseStreamEnum.PREVIEW: ReleaseStreamPath(
            PACKAGE_MANAGER_PREVIEW_URL,
            # This is intentionally stored as an OrderedDict to ensure version is resolved first so it can be passed
            # to the download_url resolver.
            OrderedDict(
                [
                    ("version", resolvers.TextResolver()),
                    (
                        "download_url",
                        "https://cdn.posit.co/package-manager/{os.packageSuffix}/{arch_identifier}/"
                        "rstudio-pm{os.packageVersionSeparator}{version}{os.packageArchSeparator}"
                        "{arch_identifier}.{os.packageSuffix}",
                    ),
                ]
            ),
        ),
        ReleaseStreamEnum.DAILY: ReleaseStreamPath(
            PACKAGE_MANAGER_DAILY_URL,
            OrderedDict(
                [
                    ("version", resolvers.TextResolver()),
                    (
                        "download_url",
                        "https://cdn.posit.co/package-manager/{os.packageSuffix}/{arch_identifier}/"
                        "rstudio-pm{os.packageVersionSeparator}{version}{os.packageArchSeparator}"
                        "{arch_identifier}.{os.packageSuffix}",
                    ),
                ]
            ),
        ),
    },
    ProductEnum.WORKBENCH: {
        ReleaseStreamEnum.RELEASE: ReleaseStreamPath(
            DOWNLOADS_JSON_URL,
            {
                "version": resolvers.StringMapPathResolver(
                    ["rstudio", "pro", "stable", "server", "installer", "{download_json_os}", "version"]
                ),
                "download_url": resolvers.StringMapPathResolver(
                    ["rstudio", "pro", "stable", "server", "installer", "{download_json_os}", "url"]
                ),
            },
        ),
        # FIXME: This stream seems out of date
        # ReleaseStreamEnum.PREVIEW: ReleaseStreamPath(
        #     DOWNLOADS_JSON_URL,
        #     {
        #         "version": resolvers.StringMapPathResolver(
        #             ["rstudio", "pro", "preview", "server", "installer", "{download_json_os}", "version"]
        #         ),
        #         "download_url": resolvers.StringMapPathResolver(
        #             ["rstudio", "pro", "preview", "server", "installer", "{download_json_os}", "url"]
        #         ),
        #     },
        # ),
        ReleaseStreamEnum.DAILY: ReleaseStreamPath(
            WORKBENCH_DAILY_URL,
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
            DOWNLOADS_JSON_URL,
            {
                "version": resolvers.StringMapPathResolver(
                    ["rstudio", "pro", "stable", "session", "installer", "{download_json_os}", "version"]
                ),
                "download_url": resolvers.StringMapPathResolver(
                    ["rstudio", "pro", "stable", "session", "installer", "{download_json_os}", "url"]
                ),
            },
        ),
        # FIXME: This stream seems out of date
        # ReleaseStreamEnum.PREVIEW: ReleaseStreamPath(
        #     DOWNLOADS_JSON_URL,
        #     {
        #         "version": resolvers.StringMapPathResolver(
        #             ["rstudio", "pro", "preview", "session", "installer", "{download_json_os}", "version"]
        #         ),
        #         "download_url": resolvers.StringMapPathResolver(
        #             ["rstudio", "pro", "preview", "session", "installer", "{download_json_os}", "url"]
        #         ),
        #     },
        # ),
        ReleaseStreamEnum.DAILY: ReleaseStreamPath(
            WORKBENCH_DAILY_URL,
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
        if product == ProductEnum.PACKAGE_MANAGER and (
            (_os.name.lower() == "ubuntu" and int(_os.majorVersion) > 22)
            or (_os.name.lower() == "debian" and int(_os.majorVersion) > 11)
        ):
            return "ubuntu64"
        elif _os.name.lower() == "ubuntu":
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


def _make_resolver_metadata(_os: BuildOS, product: ProductEnum):
    """Generates a set of metadata used in string formatting with the given OS and Product."""
    # FIXME: This does not take into account RHEL-based OS notations (x86_64 or aarch64). These may need to be set at
    #        buildtime using bash expressions.
    meta = {
        "os": _os,
        "download_json_os": _parse_download_json_os_identifier(_os, product),
        "arch_identifier": "$TARGETARCH",
    }

    if product == ProductEnum.CONNECT:
        connect_daily_os_name = _os.name.lower() + _os.majorVersion
        if _os.family == OSFamilyEnum.REDHAT_LIKE:
            if _os.majorVersion == "8":
                connect_daily_os_name = "el8"
            if _os.majorVersion == "9":
                connect_daily_os_name = "el9"
        if _os.family == OSFamilyEnum.DEBIAN_LIKE and _os.name.lower() == "debian":
            connect_daily_os_name = "ubuntu" + str(int(_os.majorVersion) * 2)
        meta["connect_daily_os_name"] = connect_daily_os_name

    return meta


def get_product_artifact_by_stream(product: ProductEnum, stream: ReleaseStreamEnum, os: BuildOS) -> ReleaseStreamResult:
    """Fetches the version and download URL for a given product, release stream, and OS."""
    if product not in product_release_stream_url_map:
        raise ValueError(f"Product {product} is not supported.")
    if stream not in product_release_stream_url_map[product]:
        raise ValueError(f"Stream {stream} is not supported for product {product}.")

    metadata = _make_resolver_metadata(os, product)

    return product_release_stream_url_map[product][stream].get(metadata)
