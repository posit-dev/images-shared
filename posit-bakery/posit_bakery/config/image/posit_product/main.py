from collections import OrderedDict
from typing import Annotated

import requests
from pydantic import BaseModel, HttpUrl, Field

from posit_bakery.config.image.build_os import BuildOS, TargetPlatform
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
    download_url: HttpUrl


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


ARCH_PLACEHOLDER = "__ARCH__"


def _get_arch_identifier(_os: BuildOS, use_placeholder: bool = False) -> str:
    """Returns the architecture identifier for the given OS.

    Args:
        _os: The build OS configuration.
        use_placeholder: If True, returns the ARCH_PLACEHOLDER constant instead of
            a concrete architecture. This is used when generating URLs that should
            be resolved at container build time using TARGETARCH.

    Returns:
        The architecture identifier string. For Debian-like systems this is 'amd64',
        for RedHat-like systems this is 'x86_64', or ARCH_PLACEHOLDER if use_placeholder is True.
    """
    if use_placeholder:
        return ARCH_PLACEHOLDER

    if _os.family == OSFamilyEnum.REDHAT_LIKE:
        return "x86_64"
    return "amd64"


def _make_resolver_metadata(_os: BuildOS, product: ProductEnum, use_arch_placeholder: bool = False):
    """Generates a set of metadata used in string formatting with the given OS and Product.

    Args:
        _os: The build OS configuration.
        product: The product enum for which to generate metadata.
        use_arch_placeholder: If True, uses ARCH_PLACEHOLDER in the metadata instead of
            concrete architecture strings. This allows URLs to be resolved at container
            build time based on TARGETARCH.
    """
    arch_identifier = _get_arch_identifier(_os, use_placeholder=use_arch_placeholder)

    meta = {
        "os": _os,
        "download_json_os": _parse_download_json_os_identifier(_os, product),
        "arch_identifier": arch_identifier,
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


def _replace_arch_in_url(url: str, _os: BuildOS) -> str:
    """Replaces architecture strings in a URL with the ARCH_PLACEHOLDER.

    This function is used to generalize URLs fetched from JSON APIs so they can be
    resolved at container build time based on TARGETARCH.

    Args:
        url: The URL containing architecture-specific strings.
        _os: The build OS configuration to determine which arch strings to replace.

    Returns:
        The URL with architecture strings replaced by ARCH_PLACEHOLDER.
    """
    if _os.family == OSFamilyEnum.REDHAT_LIKE:
        # For RPM-based systems, replace both x86_64 and aarch64
        # Note: aarch64 appears in filenames for ARM builds
        url = url.replace("x86_64", ARCH_PLACEHOLDER)
        url = url.replace("aarch64", ARCH_PLACEHOLDER)
    else:
        # For Debian-based systems, replace amd64 and arm64
        url = url.replace("amd64", ARCH_PLACEHOLDER)
        url = url.replace("arm64", ARCH_PLACEHOLDER)
    return url


def get_product_artifact_by_stream(
    product: ProductEnum, stream: ReleaseStreamEnum, os: BuildOS, use_arch_placeholder: bool = False
) -> ReleaseStreamResult:
    """Fetches the version and download URL for a given product, release stream, and OS.

    Args:
        product: The product to fetch artifacts for.
        stream: The release stream (release, daily, preview).
        os: The build OS configuration.
        use_arch_placeholder: If True, returns URLs with ARCH_PLACEHOLDER instead of
            concrete architecture strings. This allows the URL to be resolved at
            container build time based on TARGETARCH. Defaults to False for backward
            compatibility.

    Returns:
        A ReleaseStreamResult containing the version and download URL.

    Raises:
        ValueError: If the product or stream is not supported.
    """
    if product not in product_release_stream_url_map:
        raise ValueError(f"Product {product} is not supported.")
    if stream not in product_release_stream_url_map[product]:
        raise ValueError(f"Stream {stream} is not supported for product {product}.")

    # For template-based streams (like Package Manager preview/daily), we can use
    # the placeholder directly in the metadata. For JSON-based streams, we query
    # with concrete arch values and then replace them in the result.
    stream_path = product_release_stream_url_map[product][stream]
    is_template_based = _is_template_based_stream(stream_path)

    if use_arch_placeholder and is_template_based:
        # Use placeholder directly in the URL template
        metadata = _make_resolver_metadata(os, product, use_arch_placeholder=True)
    else:
        # Query with concrete arch (required for JSON lookups)
        metadata = _make_resolver_metadata(os, product, use_arch_placeholder=False)

    result = stream_path.get(metadata)

    # For JSON-based streams, post-process the URL to add placeholders
    if use_arch_placeholder and not is_template_based:
        url_with_placeholder = _replace_arch_in_url(str(result.download_url), os)
        result = ReleaseStreamResult(version=result.version, download_url=url_with_placeholder)

    return result


def _is_template_based_stream(stream_path: ReleaseStreamPath) -> bool:
    """Determines if a stream uses template-based URL construction.

    Template-based streams construct URLs using string templates with metadata
    substitution (like Package Manager preview/daily). JSON-based streams fetch
    URLs directly from JSON APIs.

    Args:
        stream_path: The ReleaseStreamPath to check.

    Returns:
        True if the stream uses template-based URL construction, False otherwise.
    """
    # Check if the download_url resolver is a string template (not a resolver object)
    download_url_resolver = stream_path.resolver_map.get("download_url")
    return isinstance(download_url_resolver, str)
