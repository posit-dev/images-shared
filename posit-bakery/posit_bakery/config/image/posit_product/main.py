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
    ReleaseChannelEnum,
    WORKBENCH_DAILY_URL,
    PACKAGE_MANAGER_DAILY_URL,
    PACKAGE_MANAGER_PREVIEW_URL,
    CONNECT_DAILY_URL,
    DOWNLOADS_JSON_URL,
)
from posit_bakery.config.image.posit_product.errors import ArtifactNotAvailableError, VersionSubstitutionError
from posit_bakery.config.shared import OSFamilyEnum
from posit_bakery.util import cached_session


class ReleaseChannelResult(BaseModel):
    """Represents a resulting artifact found in a release channel. This provides an easy validation for data we get."""

    version: Annotated[str, Field(pattern=CALVER_REGEX_PATTERN)]
    download_url: HttpUrl
    channel_latest: bool = True

    @computed_field
    @property
    def architecture_generalized_download_url(self) -> str:
        """Generalizes the architecture in the download URL to amd64/x86_64."""
        return str(self.download_url).replace("amd64", "$TARGETARCH").replace("x86_64", "$TARGETARCH")


class ReleaseChannelPath:
    """Represents a path to a release channel and a map of resolvers to extract data from the fetched data."""

    def __init__(
        self,
        channel_url: str,
        resolver_map: dict[str, resolvers.AbstractResolver | str],
        version_templatable: bool = False,
    ):
        self.channel_url = channel_url
        self.resolver_map = resolver_map
        self.version_templatable = version_templatable

    def get(self, metadata: dict, version_override: str | None = None) -> ReleaseChannelResult:
        """Fetches data from the channel URL and resolves the data using the given resolvers."""
        channel_url = self.channel_url.format_map(metadata)

        if version_override is not None and self.version_templatable:
            # PPM: build artifact URL from template, then probe it and check channel head.
            result: dict = {"version": version_override}
            url_safe_result = {f"url_safe_{k}": quote(str(v), safe="") for k, v in result.items()}
            for key, resolver in self.resolver_map.items():
                if key == "version":
                    continue
                if isinstance(resolver, str):
                    result[key] = resolver.format(**metadata, **result, **url_safe_result)

            session = cached_session()

            # Determine channel_latest by comparing override against the current channel version.
            channel_latest = False
            current_response = session.get(channel_url)
            current_response.raise_for_status()
            try:
                current_data = current_response.json()
            except requests.exceptions.JSONDecodeError:
                current_data = current_response.text
            # PPM channel endpoints return a plain-text version string, not JSON.
            # channel_latest stays False if the response is JSON (no known products do this).
            if isinstance(current_data, str):
                channel_latest = version_override.strip() == current_data.strip()

            # HEAD probe to confirm the artifact exists.
            artifact_url = str(result.get("download_url", ""))
            if artifact_url:
                head_response = session.head(artifact_url, allow_redirects=True)
                if not head_response.ok:
                    raise ArtifactNotAvailableError(
                        f"Artifact not available at {artifact_url!r}: HTTP {head_response.status_code}"
                    )

            return ReleaseChannelResult(**result, channel_latest=channel_latest)

        session = cached_session()
        response = session.get(channel_url)
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
            # Manifest-based products (Connect, Workbench): substitute the version token in
            # the manifest URL and probe the resulting artifact URL.
            manifest_version: str = result.get("version", "")
            url_str: str = result.get("download_url", "")

            # Try each known transform until we find the manifest version in the URL.
            candidates = [
                (manifest_version, version_override),
                (quote(manifest_version, safe=""), quote(version_override, safe="")),
                (manifest_version.replace("+", "-"), version_override.replace("+", "-")),
            ]
            substituted_url = None
            for needle, replacement in candidates:
                if needle and needle in url_str:
                    substituted_url = url_str.replace(needle, replacement)
                    break

            if substituted_url is None:
                raise VersionSubstitutionError(
                    f"Cannot substitute version {version_override!r} into URL {url_str!r}: "
                    f"manifest version {manifest_version!r} not found under any known transform."
                )

            result["download_url"] = substituted_url
            result["version"] = version_override

            channel_latest = version_override.strip() == manifest_version.strip()

            head_response = session.head(substituted_url, allow_redirects=True)
            if not head_response.ok:
                raise ArtifactNotAvailableError(
                    f"Artifact not available at {substituted_url!r}: HTTP {head_response.status_code}"
                )

            return ReleaseChannelResult(**result, channel_latest=channel_latest)

        return ReleaseChannelResult(**result)


# This map connects products to their respective release channels. Each release channel has a ReleaseChannelPath object
# that defines one URL to fetch data from and a map of resolvers that can be used to extract a specified property
# from the fetched data as it is expected to be formatted.
product_release_channel_url_map = {
    ProductEnum.CONNECT: {
        ReleaseChannelEnum.RELEASE: ReleaseChannelPath(
            DOWNLOADS_JSON_URL,
            {
                "version": resolvers.StringMapPathResolver(["connect", "installer", "{download_json_os}", "version"]),
                "download_url": resolvers.StringMapPathResolver(["connect", "installer", "{download_json_os}", "url"]),
            },
        ),
        ReleaseChannelEnum.DAILY: ReleaseChannelPath(
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
        ReleaseChannelEnum.RELEASE: ReleaseChannelPath(
            DOWNLOADS_JSON_URL,
            {
                "version": resolvers.StringMapPathResolver(["rspm", "installer", "{download_json_os}", "version"]),
                "download_url": resolvers.StringMapPathResolver(["rspm", "installer", "{download_json_os}", "url"]),
            },
        ),
        ReleaseChannelEnum.PREVIEW: ReleaseChannelPath(
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
            version_templatable=True,
        ),
        ReleaseChannelEnum.DAILY: ReleaseChannelPath(
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
            version_templatable=True,
        ),
    },
    ProductEnum.WORKBENCH: {
        ReleaseChannelEnum.RELEASE: ReleaseChannelPath(
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
        ReleaseChannelEnum.DAILY: ReleaseChannelPath(
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
        ReleaseChannelEnum.RELEASE: ReleaseChannelPath(
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
        ReleaseChannelEnum.DAILY: ReleaseChannelPath(
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


def get_product_artifact_by_channel(
    product: ProductEnum,
    channel: ReleaseChannelEnum,
    os: BuildOS,
    version_override: str | None = None,
    release_branch: str = "latest",
) -> ReleaseChannelResult:
    """Fetches the version and download URL for a given product, release channel, and OS."""
    if product not in product_release_channel_url_map:
        raise ValueError(f"Product {product} is not supported.")
    if channel not in product_release_channel_url_map[product]:
        raise ValueError(f"Channel {channel} is not supported for product {product}.")

    metadata = _make_resolver_metadata(os, product)
    metadata["release_branch"] = release_branch

    return product_release_channel_url_map[product][channel].get(metadata, version_override)
