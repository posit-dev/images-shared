from collections import OrderedDict
from typing import Annotated
from urllib.parse import quote

import requests
from pydantic import BaseModel, Field, computed_field, HttpUrl

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
    download_url: HttpUrl

    @computed_field
    @property
    def architecture_generalized_download_url(self) -> str:
        """Generalizes the architecture in the download URL to amd64/x86_64."""
        return str(self.download_url).replace("amd64", "$TARGETARCH").replace("x86_64", "$TARGETARCH")


class ReleaseStreamPath:
    """Represents a path to a release stream and a map of resolvers to extract data from the fetched data."""

    def __init__(self, stream_url: str, resolver_map: dict[str, resolvers.AbstractResolver | str]):
        self.stream_url = stream_url
        self.resolver_map = resolver_map

    def get(self, metadata: dict, version_override: str | None = None) -> ReleaseStreamResult:
        """Fetches data from the stream URL and resolves the data using the given resolvers.

        When ``version_override`` is set, resolvers still run unchanged (we need the upstream
        version to know what to rewrite). After resolution, ``result["version"]`` is replaced
        with the override and any occurrence of the upstream version in ``download_url`` is
        rewritten to the override form. See :func:`_apply_version_override` for the encodings
        we handle.
        """
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
                # Provide URL-safe versions of all result values for use in URL templates
                url_safe_result = {f"url_safe_{k}": quote(str(v), safe="") for k, v in result.items()}
                result[key] = resolver.format(**metadata, **result, **url_safe_result)
            elif isinstance(resolver, resolvers.AbstractResolver):
                resolver.set_metadata(metadata)
                result[key] = resolver.resolve(data)

        if version_override is not None:
            _apply_version_override(result, version_override)

        return ReleaseStreamResult(**result)


def _apply_version_override(result: dict, version_override: str) -> None:
    """Rewrite ``result`` in place to reflect a caller-supplied version override.

    Replaces ``result["version"]`` with the override and rewrites every occurrence of
    the upstream version in ``download_url`` so the URL points at the override's artifact.
    The rewrite covers the three encodings products embed the version in URLs:

      - **raw** (e.g. ``2026.05.0-dev+148-gSHA``) — rare in URLs but possible
      - **URL-encoded** (e.g. ``2026.05.0-dev%2B148-gSHA``) — Connect, PPM
      - **tag-safe** with ``+`` replaced by ``-`` (e.g. ``2026.05.0-dev-148-gSHA``) — Workbench

    Resolvers themselves remain declarative and untouched; this is a pure post-resolution
    rewrite. If the upstream version doesn't appear in the URL in any of these forms,
    the URL is left as-is and the build will download the upstream artifact — at which
    point the caller can detect the mismatch via the resulting image's contents.
    """
    upstream_version = result.get("version", "")
    result["version"] = version_override
    if not upstream_version or not isinstance(result.get("download_url"), str):
        return
    url = result["download_url"]
    url = url.replace(upstream_version, version_override)
    url = url.replace(quote(upstream_version, safe=""), quote(version_override, safe=""))
    url = url.replace(upstream_version.replace("+", "-"), version_override.replace("+", "-"))
    result["download_url"] = url


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
                        "rstudio-pm{os.packageVersionSeparator}{url_safe_version}{os.packageArchSeparator}"
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
                        "rstudio-pm{os.packageVersionSeparator}{url_safe_version}{os.packageArchSeparator}"
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

    arch_identifier = "amd64"
    if _os.family == OSFamilyEnum.REDHAT_LIKE:
        arch_identifier = "x86_64"

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


def get_product_artifact_by_stream(
    product: ProductEnum,
    stream: ReleaseStreamEnum,
    os: BuildOS,
    generalize_arch: bool = True,
    version_override: str | None = None,
) -> ReleaseStreamResult:
    """Fetches the version and download URL for a given product, release stream, and OS.

    When ``version_override`` is set, the returned ``version`` is the override and the
    ``download_url`` is rewritten so it points at the override's artifact (across all
    three URL encoding styles products use).
    """
    if product not in product_release_stream_url_map:
        raise ValueError(f"Product {product} is not supported.")
    if stream not in product_release_stream_url_map[product]:
        raise ValueError(f"Stream {stream} is not supported for product {product}.")

    metadata = _make_resolver_metadata(os, product)

    return product_release_stream_url_map[product][stream].get(metadata, version_override=version_override)
