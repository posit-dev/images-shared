import pytest

from posit_bakery.config.image.build_os import SUPPORTED_OS, BuildOS
from posit_bakery.config.image.posit_product.const import ProductEnum, ReleaseChannelEnum, ReleaseStreamEnum
from posit_bakery.config.image.posit_product.errors import ArtifactNotAvailableError, VersionSubstitutionError
from posit_bakery.config.image.posit_product.main import (
    _parse_download_json_os_identifier,
    _make_resolver_metadata,
    get_product_artifact_by_channel,
    ReleaseChannelResult,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
    pytest.mark.product_version,
]

helper_test_collection = [
    *[
        pytest.param(
            SUPPORTED_OS[_os_name][_os_version],
            ProductEnum.CONNECT,
            {
                "download_json_os": "noble",
                "connect_daily_os_name": "ubuntu24",
                "os": SUPPORTED_OS[_os_name][_os_version],
                "arch_identifier": "amd64",
            },
            id=f"connect-{_os_name}-{_os_version}",
        )
        for _os_name, _os_version in [("debian", "12"), ("ubuntu", "24")]
    ],
    *[
        pytest.param(
            SUPPORTED_OS[_os_name][_os_version],
            ProductEnum.PACKAGE_MANAGER,
            {
                "download_json_os": "ubuntu64",
                "os": SUPPORTED_OS[_os_name][_os_version],
                "arch_identifier": "amd64",
            },
            id=f"package-manager-{_os_name}-{_os_version}",
        )
        for _os_name, _os_version in [("debian", "12"), ("ubuntu", "24")]
    ],
    *[
        pytest.param(
            SUPPORTED_OS[_os_name][_os_version],
            product,
            {
                "download_json_os": "noble",
                "os": SUPPORTED_OS[_os_name][_os_version],
                "arch_identifier": "amd64",
            },
            id=f"{product}-{_os_name}-{_os_version}",
        )
        for product in [ProductEnum.WORKBENCH, ProductEnum.WORKBENCH_SESSION]
        for _os_name, _os_version in [("debian", "12"), ("ubuntu", "24")]
    ],
    *[
        pytest.param(
            SUPPORTED_OS[_os_name][_os_version],
            ProductEnum.POSITRON,
            {
                "download_json_os": "noble",
                "os": SUPPORTED_OS[_os_name][_os_version],
                "arch_identifier": "amd64",
                "positron_cdn_arch": "x86_64",
                "positron_pkg_arch": "x64",
            },
            id=f"positron-{_os_name}-{_os_version}",
        )
        for _os_name, _os_version in [("debian", "12"), ("ubuntu", "24")]
    ],
    *[
        pytest.param(
            SUPPORTED_OS[_os_name][_os_version],
            ProductEnum.POSITRON,
            {
                "download_json_os": "jammy",
                "os": SUPPORTED_OS[_os_name][_os_version],
                "arch_identifier": "amd64",
                "positron_cdn_arch": "x86_64",
                "positron_pkg_arch": "x64",
            },
            id=f"positron-{_os_name}-{_os_version}",
        )
        for _os_name, _os_version in [("debian", "11"), ("ubuntu", "22")]
    ],
    *[
        pytest.param(
            SUPPORTED_OS[_os_name][_os_version],
            ProductEnum.CONNECT,
            {
                "download_json_os": "jammy",
                "connect_daily_os_name": "ubuntu22",
                "os": SUPPORTED_OS[_os_name][_os_version],
                "arch_identifier": "amd64",
            },
            id=f"connect-{_os_name}-{_os_version}",
        )
        for _os_name, _os_version in [("debian", "11"), ("ubuntu", "22")]
    ],
    *[
        pytest.param(
            SUPPORTED_OS[_os_name][_os_version],
            product,
            {"download_json_os": "jammy", "os": SUPPORTED_OS[_os_name][_os_version], "arch_identifier": "amd64"},
            id=f"{product}-{_os_name}-{_os_version}",
        )
        for product in [ProductEnum.PACKAGE_MANAGER, ProductEnum.WORKBENCH, ProductEnum.WORKBENCH_SESSION]
        for _os_name, _os_version in [("debian", "11"), ("ubuntu", "22")]
    ],
    *[
        pytest.param(
            SUPPORTED_OS[_os_name][_os_version],
            ProductEnum.CONNECT,
            {
                "download_json_os": "redhat8",
                "connect_daily_os_name": "el8",
                "os": SUPPORTED_OS[_os_name][_os_version],
                "arch_identifier": "x86_64",
            },
            id=f"connect-{_os_name}-{_os_version}",
        )
        for _os_name, _os_version in [("rocky", "8"), ("alma", "8"), ("rhel", "8")]
    ],
    *[
        pytest.param(
            SUPPORTED_OS[_os_name][_os_version],
            ProductEnum.PACKAGE_MANAGER,
            {"download_json_os": "fedora28", "os": SUPPORTED_OS[_os_name][_os_version], "arch_identifier": "x86_64"},
            id=f"package-manager-{_os_name}-{_os_version}",
        )
        for _os_name, _os_version in [("rocky", "8"), ("alma", "8"), ("rhel", "8")]
    ],
    *[
        pytest.param(
            SUPPORTED_OS[_os_name][_os_version],
            product,
            {"download_json_os": "rhel8", "os": SUPPORTED_OS[_os_name][_os_version], "arch_identifier": "x86_64"},
            id=f"{product}-{_os_name}-{_os_version}",
        )
        for product in [ProductEnum.WORKBENCH, ProductEnum.WORKBENCH_SESSION]
        for _os_name, _os_version in [("rocky", "8"), ("alma", "8"), ("rhel", "8")]
    ],
    *[
        pytest.param(
            SUPPORTED_OS[_os_name][_os_version],
            ProductEnum.CONNECT,
            {
                "download_json_os": "rhel9",
                "connect_daily_os_name": "el9",
                "os": SUPPORTED_OS[_os_name][_os_version],
                "arch_identifier": "x86_64",
            },
            id=f"connect-{_os_name}-{_os_version}",
        )
        for _os_name, _os_version in [("rocky", "9"), ("alma", "9"), ("rhel", "9")]
    ],
    *[
        pytest.param(
            SUPPORTED_OS[_os_name][_os_version],
            product,
            {"download_json_os": "rhel9", "os": SUPPORTED_OS[_os_name][_os_version], "arch_identifier": "x86_64"},
            id=f"{product}-{_os_name}-{_os_version}",
        )
        for product in [ProductEnum.PACKAGE_MANAGER, ProductEnum.WORKBENCH, ProductEnum.WORKBENCH_SESSION]
        for _os_name, _os_version in [("rocky", "9"), ("alma", "9"), ("rhel", "9")]
    ],
    *[
        pytest.param(
            SUPPORTED_OS["scratch"],
            ProductEnum.CONNECT,
            {
                "download_json_os": "multi",
                "connect_daily_os_name": "scratch",
                "os": SUPPORTED_OS["scratch"],
                "arch_identifier": "amd64",
            },
            id="connect-scratch",
        )
    ],
    *[
        pytest.param(
            SUPPORTED_OS["scratch"],
            product,
            {"download_json_os": "multi", "os": SUPPORTED_OS["scratch"], "arch_identifier": "amd64"},
            id=f"{product}-scratch",
        )
        for product in [ProductEnum.PACKAGE_MANAGER, ProductEnum.WORKBENCH, ProductEnum.WORKBENCH_SESSION]
    ],
]


class TestReleaseChannelEnum:
    def test_channel_enum_has_same_values_as_stream_enum(self):
        assert ReleaseChannelEnum.DAILY == ReleaseStreamEnum.DAILY
        assert ReleaseChannelEnum.PREVIEW == ReleaseStreamEnum.PREVIEW
        assert ReleaseChannelEnum.RELEASE == ReleaseStreamEnum.RELEASE

    def test_stream_enum_is_alias_for_channel_enum(self):
        assert ReleaseStreamEnum is ReleaseChannelEnum


class TestReleaseChannelResult:
    @pytest.mark.parametrize(
        "download_url,expected_url",
        [
            pytest.param(
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect_2025.03.0~ubuntu24_amd64.deb",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect_2025.03.0~ubuntu24_$TARGETARCH.deb",
                id="debian-url",
            ),
            pytest.param(
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect-2025.03.0.el8.x86_64.rpm",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect-2025.03.0.el8.$TARGETARCH.rpm",
                id="rhel-url",
            ),
        ],
    )
    def test_architecture_generalized_download_url(self, download_url, expected_url):
        """Tests for architecture_generalized_download_url property of ReleaseChannelResult"""
        result = ReleaseChannelResult(version="1.0.0", download_url=download_url)
        assert str(result.architecture_generalized_download_url) == expected_url


class TestHelpers:
    @pytest.mark.parametrize(
        "_os,product,expected",
        helper_test_collection,
    )
    def test__parse_download_json_os_identifier(self, _os: BuildOS, product: ProductEnum, expected: dict):
        """Tests for supported OSes against parsing their associated download.json identifiers"""
        output = _parse_download_json_os_identifier(_os, product)
        assert output == expected["download_json_os"]

    @pytest.mark.parametrize(
        "_os,product,expected",
        helper_test_collection,
    )
    def test__make_resolver_metadata(self, _os: BuildOS, product: ProductEnum, expected: dict):
        """Tests for supported OSes against parsing their associated download.json identifiers"""
        output = _make_resolver_metadata(_os, product)
        assert output == expected


class TestGetProductArtifactByChannel:
    def test_bad_product(self):
        """Test that an invalid product raises an error"""
        with pytest.raises(ValueError):
            get_product_artifact_by_channel("bad", "daily", SUPPORTED_OS["ubuntu"]["22"])

    def test_bad_channel(self):
        """Test that an invalid channel raises an error"""
        with pytest.raises(ValueError):
            get_product_artifact_by_channel("connect", "preview", SUPPORTED_OS["ubuntu"]["22"])

    @pytest.mark.parametrize(
        "_os,expected_version,expected_url",
        [
            pytest.param(
                SUPPORTED_OS["debian"]["12"],
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect_2025.03.0~ubuntu24_amd64.deb",
                id="debian-12",
            ),
            pytest.param(
                SUPPORTED_OS["debian"]["11"],
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect_2025.03.0~ubuntu22_amd64.deb",
                id="debian-11",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["24"],
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect_2025.03.0~ubuntu24_amd64.deb",
                id="ubuntu-24",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["22"],
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect_2025.03.0~ubuntu22_amd64.deb",
                id="ubuntu-22",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["8"],
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect-2025.03.0.el8.x86_64.rpm",
                id="alma-8",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["8"],
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect-2025.03.0.el8.x86_64.rpm",
                id="rocky-8",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["8"],
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect-2025.03.0.el8.x86_64.rpm",
                id="rhel-8",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["9"],
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect-2025.03.0.el9.x86_64.rpm",
                id="alma-9",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["9"],
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect-2025.03.0.el9.x86_64.rpm",
                id="rocky-9",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["9"],
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect-2025.03.0.el9.x86_64.rpm",
                id="rhel-9",
            ),
        ],
    )
    def test_connect_release(self, patch_requests_get, _os: BuildOS, expected_version: str, expected_url: str):
        """Test that the correct URL is returned for a release version of Connect Release"""
        output = get_product_artifact_by_channel(ProductEnum.CONNECT, ReleaseStreamEnum.RELEASE, _os)
        assert output.version == expected_version
        assert str(output.download_url) == expected_url

    @pytest.mark.parametrize(
        "_os,expected_version,expected_url",
        [
            pytest.param(
                SUPPORTED_OS["debian"]["12"],
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/"
                "rstudio-connect_2025.04.0-dev%2B10-gbe0a4a3d31~ubuntu24_amd64.deb",
                id="debian-12",
            ),
            pytest.param(
                SUPPORTED_OS["debian"]["11"],
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/"
                "rstudio-connect_2025.04.0-dev%2B10-gbe0a4a3d31~ubuntu22_amd64.deb",
                id="debian-11",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["24"],
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/rstudio-connect_2025.04.0-dev%2B10-gbe0a4a3d31~"
                "ubuntu24_amd64.deb",
                id="ubuntu-24",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["22"],
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/rstudio-connect_2025.04.0-dev%2B10-gbe0a4a3d31~"
                "ubuntu22_amd64.deb",
                id="ubuntu-22",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["8"],
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/rstudio-connect-2025.04.0-dev%2B10-gbe0a4a3d31.el8.x86_64.rpm",
                id="alma-8",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["8"],
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/rstudio-connect-2025.04.0-dev%2B10-gbe0a4a3d31.el8.x86_64.rpm",
                id="rocky-8",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["8"],
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/rstudio-connect-2025.04.0-dev%2B10-gbe0a4a3d31.el8.x86_64.rpm",
                id="rhel-8",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["9"],
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/rstudio-connect-2025.04.0-dev%2B10-gbe0a4a3d31.el9.x86_64.rpm",
                id="alma-9",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["9"],
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/rstudio-connect-2025.04.0-dev%2B10-gbe0a4a3d31.el9.x86_64.rpm",
                id="rocky-9",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["9"],
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/rstudio-connect-2025.04.0-dev%2B10-gbe0a4a3d31.el9.x86_64.rpm",
                id="rhel-9",
            ),
        ],
    )
    def test_connect_daily(self, patch_requests_get, _os: BuildOS, expected_version: str, expected_url: str):
        """Test that the correct URL is returned for a release version of Connect Daily"""
        output = get_product_artifact_by_channel(ProductEnum.CONNECT, ReleaseStreamEnum.DAILY, _os)
        assert output.version == expected_version
        assert str(output.download_url) == expected_url

    @pytest.mark.parametrize(
        "_os,expected_version,expected_url",
        [
            pytest.param(
                SUPPORTED_OS["debian"]["12"],
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/deb/amd64/rstudio-pm_2024.11.0-7_amd64.deb",
                id="debian-12",
            ),
            pytest.param(
                SUPPORTED_OS["debian"]["11"],
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/deb/amd64/rstudio-pm_2024.11.0-7_amd64.deb",
                id="debian-11",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["24"],
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/deb/amd64/rstudio-pm_2024.11.0-7_amd64.deb",
                id="ubuntu-24",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["22"],
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/deb/amd64/rstudio-pm_2024.11.0-7_amd64.deb",
                id="ubuntu-22",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["8"],
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/rpm/x86_64/rstudio-pm-2024.11.0-7.x86_64.rpm",
                id="alma-8",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["8"],
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/rpm/x86_64/rstudio-pm-2024.11.0-7.x86_64.rpm",
                id="rocky-8",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["8"],
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/rpm/x86_64/rstudio-pm-2024.11.0-7.x86_64.rpm",
                id="rhel-8",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["9"],
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/rpm/x86_64/rstudio-pm-2024.11.0-7.x86_64.rpm",
                id="alma-9",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["9"],
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/rpm/x86_64/rstudio-pm-2024.11.0-7.x86_64.rpm",
                id="rocky-9",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["9"],
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/rpm/x86_64/rstudio-pm-2024.11.0-7.x86_64.rpm",
                id="rhel-9",
            ),
        ],
    )
    def test_package_manager_release(self, patch_requests_get, _os: BuildOS, expected_version: str, expected_url: str):
        """Test that the correct URL is returned for a release version of PPM Release"""
        output = get_product_artifact_by_channel(ProductEnum.PACKAGE_MANAGER, ReleaseStreamEnum.RELEASE, _os)
        assert output.version == expected_version
        assert str(output.download_url) == expected_url

    @pytest.mark.parametrize(
        "_os,expected_version,expected_url",
        [
            pytest.param(
                SUPPORTED_OS["debian"]["12"],
                "2026.01.0-dev+167-gd27bbec1d7",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2026.01.0-dev%2B167-gd27bbec1d7_amd64.deb",
                id="debian-12",
            ),
            pytest.param(
                SUPPORTED_OS["debian"]["11"],
                "2026.01.0-dev+167-gd27bbec1d7",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2026.01.0-dev%2B167-gd27bbec1d7_amd64.deb",
                id="debian-11",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["24"],
                "2026.01.0-dev+167-gd27bbec1d7",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2026.01.0-dev%2B167-gd27bbec1d7_amd64.deb",
                id="ubuntu-24",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["22"],
                "2026.01.0-dev+167-gd27bbec1d7",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2026.01.0-dev%2B167-gd27bbec1d7_amd64.deb",
                id="ubuntu-22",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["8"],
                "2026.01.0-dev+167-gd27bbec1d7",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2026.01.0-dev%2B167-gd27bbec1d7.x86_64.rpm",
                id="alma-8",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["8"],
                "2026.01.0-dev+167-gd27bbec1d7",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2026.01.0-dev%2B167-gd27bbec1d7.x86_64.rpm",
                id="rocky-8",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["8"],
                "2026.01.0-dev+167-gd27bbec1d7",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2026.01.0-dev%2B167-gd27bbec1d7.x86_64.rpm",
                id="rhel-8",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["9"],
                "2026.01.0-dev+167-gd27bbec1d7",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2026.01.0-dev%2B167-gd27bbec1d7.x86_64.rpm",
                id="alma-9",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["9"],
                "2026.01.0-dev+167-gd27bbec1d7",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2026.01.0-dev%2B167-gd27bbec1d7.x86_64.rpm",
                id="rocky-9",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["9"],
                "2026.01.0-dev+167-gd27bbec1d7",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2026.01.0-dev%2B167-gd27bbec1d7.x86_64.rpm",
                id="rhel-9",
            ),
        ],
    )
    def test_package_manager_preview(self, patch_requests_get, _os: BuildOS, expected_version: str, expected_url: str):
        """Test that the correct URL is returned for a release version of PPM Preview"""
        output = get_product_artifact_by_channel(ProductEnum.PACKAGE_MANAGER, ReleaseStreamEnum.PREVIEW, _os)
        assert output.version == expected_version
        assert str(output.download_url) == expected_url

    @pytest.mark.parametrize(
        "_os,expected_version,expected_url",
        [
            pytest.param(
                SUPPORTED_OS["debian"]["12"],
                "2026.02.0-dev+89-ga1b2c3d4e5",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2026.02.0-dev%2B89-ga1b2c3d4e5_amd64.deb",
                id="debian-12",
            ),
            pytest.param(
                SUPPORTED_OS["debian"]["11"],
                "2026.02.0-dev+89-ga1b2c3d4e5",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2026.02.0-dev%2B89-ga1b2c3d4e5_amd64.deb",
                id="debian-11",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["24"],
                "2026.02.0-dev+89-ga1b2c3d4e5",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2026.02.0-dev%2B89-ga1b2c3d4e5_amd64.deb",
                id="ubuntu-24",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["22"],
                "2026.02.0-dev+89-ga1b2c3d4e5",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2026.02.0-dev%2B89-ga1b2c3d4e5_amd64.deb",
                id="ubuntu-22",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["8"],
                "2026.02.0-dev+89-ga1b2c3d4e5",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2026.02.0-dev%2B89-ga1b2c3d4e5.x86_64.rpm",
                id="alma-8",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["8"],
                "2026.02.0-dev+89-ga1b2c3d4e5",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2026.02.0-dev%2B89-ga1b2c3d4e5.x86_64.rpm",
                id="rocky-8",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["8"],
                "2026.02.0-dev+89-ga1b2c3d4e5",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2026.02.0-dev%2B89-ga1b2c3d4e5.x86_64.rpm",
                id="rhel-8",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["9"],
                "2026.02.0-dev+89-ga1b2c3d4e5",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2026.02.0-dev%2B89-ga1b2c3d4e5.x86_64.rpm",
                id="alma-9",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["9"],
                "2026.02.0-dev+89-ga1b2c3d4e5",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2026.02.0-dev%2B89-ga1b2c3d4e5.x86_64.rpm",
                id="rocky-9",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["9"],
                "2026.02.0-dev+89-ga1b2c3d4e5",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2026.02.0-dev%2B89-ga1b2c3d4e5.x86_64.rpm",
                id="rhel-9",
            ),
        ],
    )
    def test_package_manager_daily(self, patch_requests_get, _os: BuildOS, expected_version: str, expected_url: str):
        """Test that the correct URL is returned for a release version of PPM Daily"""
        output = get_product_artifact_by_channel(ProductEnum.PACKAGE_MANAGER, ReleaseStreamEnum.DAILY, _os)
        assert output.version == expected_version
        assert str(output.download_url) == expected_url

    @pytest.mark.parametrize(
        "_os,expected_version,expected_url,expected_session_url",
        [
            pytest.param(
                SUPPORTED_OS["debian"]["12"],
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/jammy/amd64/rstudio-workbench-2024.12.1-563.pro5-amd64.deb",
                "https://download1.rstudio.org/session/jammy/amd64/rsp-session-jammy-2024.12.1-563.pro5-amd64.tar.gz",
                id="debian-12",
            ),
            pytest.param(
                SUPPORTED_OS["debian"]["11"],
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/jammy/amd64/rstudio-workbench-2024.12.1-563.pro5-amd64.deb",
                "https://download1.rstudio.org/session/jammy/amd64/rsp-session-jammy-2024.12.1-563.pro5-amd64.tar.gz",
                id="debian-11",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["24"],
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/jammy/amd64/rstudio-workbench-2024.12.1-563.pro5-amd64.deb",
                "https://download1.rstudio.org/session/jammy/amd64/rsp-session-jammy-2024.12.1-563.pro5-amd64.tar.gz",
                id="ubuntu-24",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["22"],
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/jammy/amd64/rstudio-workbench-2024.12.1-563.pro5-amd64.deb",
                "https://download1.rstudio.org/session/jammy/amd64/rsp-session-jammy-2024.12.1-563.pro5-amd64.tar.gz",
                id="ubuntu-22",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["8"],
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/rhel8/x86_64/"
                "rstudio-workbench-rhel-2024.12.1-563.pro5-x86_64.rpm",
                "https://download1.rstudio.org/session/rhel8/x86_64/rsp-session-rhel8-2024.12.1-563.pro5-x86_64.tar.gz",
                id="alma-8",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["8"],
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/rhel8/x86_64/"
                "rstudio-workbench-rhel-2024.12.1-563.pro5-x86_64.rpm",
                "https://download1.rstudio.org/session/rhel8/x86_64/rsp-session-rhel8-2024.12.1-563.pro5-x86_64.tar.gz",
                id="rocky-8",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["8"],
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/rhel8/x86_64/"
                "rstudio-workbench-rhel-2024.12.1-563.pro5-x86_64.rpm",
                "https://download1.rstudio.org/session/rhel8/x86_64/rsp-session-rhel8-2024.12.1-563.pro5-x86_64.tar.gz",
                id="rhel-8",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["9"],
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/rhel9/x86_64/"
                "rstudio-workbench-rhel-2024.12.1-563.pro5-x86_64.rpm",
                "https://download1.rstudio.org/session/rhel9/x86_64/rsp-session-rhel9-2024.12.1-563.pro5-x86_64.tar.gz",
                id="alma-9",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["9"],
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/rhel9/x86_64/"
                "rstudio-workbench-rhel-2024.12.1-563.pro5-x86_64.rpm",
                "https://download1.rstudio.org/session/rhel9/x86_64/rsp-session-rhel9-2024.12.1-563.pro5-x86_64.tar.gz",
                id="rocky-9",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["9"],
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/rhel9/x86_64/rstudio-workbench-rhel-2024.12.1-563.pro5-x86_64.rpm",
                "https://download1.rstudio.org/session/rhel9/x86_64/rsp-session-rhel9-2024.12.1-563.pro5-x86_64.tar.gz",
                id="rhel-9",
            ),
        ],
    )
    def test_workbench_release(
        self, patch_requests_get, _os: BuildOS, expected_version: str, expected_url: str, expected_session_url: str
    ):
        """Test that the correct URL is returned for a release version of Workbench Release"""
        output = get_product_artifact_by_channel(ProductEnum.WORKBENCH, ReleaseStreamEnum.RELEASE, _os)
        assert output.version == expected_version
        assert str(output.download_url) == expected_url

        output = get_product_artifact_by_channel(ProductEnum.WORKBENCH_SESSION, ReleaseStreamEnum.RELEASE, _os)
        assert output.version == expected_version
        assert str(output.download_url) == expected_session_url

    @pytest.mark.parametrize(
        "_os,expected_version,expected_url,expected_session_url",
        [
            pytest.param(
                SUPPORTED_OS["debian"]["12"],
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/jammy/amd64/"
                "rstudio-workbench-2025.04.0-daily-404.pro4-amd64.deb",
                "https://s3.amazonaws.com/rstudio-ide-build/session/jammy/amd64/"
                "rsp-session-jammy-2025.04.0-daily-404.pro4-amd64.tar.gz",
                id="debian-12",
            ),
            pytest.param(
                SUPPORTED_OS["debian"]["11"],
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/jammy/amd64/"
                "rstudio-workbench-2025.04.0-daily-404.pro4-amd64.deb",
                "https://s3.amazonaws.com/rstudio-ide-build/session/jammy/amd64/"
                "rsp-session-jammy-2025.04.0-daily-404.pro4-amd64.tar.gz",
                id="debian-11",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["24"],
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/jammy/amd64/"
                "rstudio-workbench-2025.04.0-daily-404.pro4-amd64.deb",
                "https://s3.amazonaws.com/rstudio-ide-build/session/jammy/amd64/"
                "rsp-session-jammy-2025.04.0-daily-404.pro4-amd64.tar.gz",
                id="ubuntu-24",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["22"],
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/jammy/amd64/"
                "rstudio-workbench-2025.04.0-daily-404.pro4-amd64.deb",
                "https://s3.amazonaws.com/rstudio-ide-build/session/jammy/amd64/"
                "rsp-session-jammy-2025.04.0-daily-404.pro4-amd64.tar.gz",
                id="ubuntu-22",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["8"],
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/rhel8/x86_64/"
                "rstudio-workbench-rhel-2025.04.0-daily-404.pro4-x86_64.rpm",
                "https://s3.amazonaws.com/rstudio-ide-build/session/rhel8/x86_64/"
                "rsp-session-rhel8-2025.04.0-daily-404.pro4-x86_64.tar.gz",
                id="alma-8",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["8"],
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/rhel8/x86_64/"
                "rstudio-workbench-rhel-2025.04.0-daily-404.pro4-x86_64.rpm",
                "https://s3.amazonaws.com/rstudio-ide-build/session/rhel8/x86_64/"
                "rsp-session-rhel8-2025.04.0-daily-404.pro4-x86_64.tar.gz",
                id="rocky-8",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["8"],
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/rhel8/x86_64/"
                "rstudio-workbench-rhel-2025.04.0-daily-404.pro4-x86_64.rpm",
                "https://s3.amazonaws.com/rstudio-ide-build/session/rhel8/x86_64/"
                "rsp-session-rhel8-2025.04.0-daily-404.pro4-x86_64.tar.gz",
                id="rhel-8",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["9"],
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/rhel9/x86_64/"
                "rstudio-workbench-rhel-2025.04.0-daily-404.pro4-x86_64.rpm",
                "https://s3.amazonaws.com/rstudio-ide-build/session/rhel9/x86_64/"
                "rsp-session-rhel9-2025.04.0-daily-404.pro4-x86_64.tar.gz",
                id="alma-9",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["9"],
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/rhel9/x86_64/"
                "rstudio-workbench-rhel-2025.04.0-daily-404.pro4-x86_64.rpm",
                "https://s3.amazonaws.com/rstudio-ide-build/session/rhel9/x86_64/"
                "rsp-session-rhel9-2025.04.0-daily-404.pro4-x86_64.tar.gz",
                id="rocky-9",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["9"],
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/rhel9/x86_64/"
                "rstudio-workbench-rhel-2025.04.0-daily-404.pro4-x86_64.rpm",
                "https://s3.amazonaws.com/rstudio-ide-build/session/rhel9/x86_64/"
                "rsp-session-rhel9-2025.04.0-daily-404.pro4-x86_64.tar.gz",
                id="rhel-9",
            ),
        ],
    )
    def test_workbench_daily(
        self, patch_requests_get, _os: BuildOS, expected_version: str, expected_url: str, expected_session_url: str
    ):
        """Test that the correct URL is returned for a release version of Workbench Daily"""
        output = get_product_artifact_by_channel(ProductEnum.WORKBENCH, ReleaseStreamEnum.DAILY, _os)
        assert output.version == expected_version
        assert str(output.download_url) == expected_url

        output = get_product_artifact_by_channel(ProductEnum.WORKBENCH_SESSION, ReleaseStreamEnum.DAILY, _os)
        assert output.version == expected_version
        assert str(output.download_url) == expected_session_url


class TestGetProductArtifactByChannelReleaseBranch:
    """release_branch is passed through to the Workbench daily URL."""

    def test_default_release_branch_uses_latest(self, mocker):
        from test.config.conftest import patch_testdata_response

        mock_session = mocker.patch("posit_bakery.config.image.posit_product.main.cached_session")
        mock_session.return_value.get.side_effect = patch_testdata_response
        mock_session.return_value.get.return_value.raise_for_status.return_value = None

        get_product_artifact_by_channel(ProductEnum.WORKBENCH, ReleaseChannelEnum.DAILY, SUPPORTED_OS["ubuntu"]["24"])

        called_url = mock_session.return_value.get.call_args[0][0]
        assert called_url == "https://dailies.rstudio.com/rstudio/latest/index.json"

    def test_named_release_branch_formats_url(self, mocker):
        from test.config.conftest import patch_testdata_response

        mock_session = mocker.patch("posit_bakery.config.image.posit_product.main.cached_session")
        mock_session.return_value.get.side_effect = patch_testdata_response
        mock_session.return_value.get.return_value.raise_for_status.return_value = None

        get_product_artifact_by_channel(
            ProductEnum.WORKBENCH,
            ReleaseChannelEnum.DAILY,
            SUPPORTED_OS["ubuntu"]["24"],
            release_branch="apple-blossom",
        )

        called_url = mock_session.return_value.get.call_args[0][0]
        assert called_url == "https://dailies.rstudio.com/rstudio/apple-blossom/index.json"


class TestDispatchOverride:
    def test_ppm_daily_override_uses_template_url(self, mocker):
        """PPM override builds the artifact URL from the template and probes it."""
        from test.config.conftest import patch_testdata_response

        mock_session = mocker.patch("posit_bakery.config.image.posit_product.main.cached_session")
        mock_session.return_value.get.side_effect = patch_testdata_response
        mock_session.return_value.head.return_value.ok = True

        override = "2026.05.0-dev+185-g8a23833f57"
        result = get_product_artifact_by_channel(
            ProductEnum.PACKAGE_MANAGER,
            ReleaseChannelEnum.DAILY,
            SUPPORTED_OS["ubuntu"]["24"],
            version_override=override,
        )
        assert result.version == override
        assert "2026.05.0-dev%2B185-g8a23833f57" in str(result.download_url)
        # Override differs from fixture head (2026.02.0-dev+89-...), so not channel latest.
        assert result.channel_latest is False
        mock_session.return_value.head.assert_called_once()

    def test_ppm_preview_override_uses_template_url(self, mocker):
        """PPM preview override builds the URL from template, probes, checks channel head."""
        from test.config.conftest import patch_testdata_response

        mock_session = mocker.patch("posit_bakery.config.image.posit_product.main.cached_session")
        mock_session.return_value.get.side_effect = patch_testdata_response
        mock_session.return_value.head.return_value.ok = True

        override = "2026.05.0-dev+185-g8a23833f57"
        result = get_product_artifact_by_channel(
            ProductEnum.PACKAGE_MANAGER,
            ReleaseChannelEnum.PREVIEW,
            SUPPORTED_OS["ubuntu"]["24"],
            version_override=override,
        )
        assert result.version == override
        assert result.channel_latest is False

    def test_connect_daily_override_substitutes_url(self, patch_requests_get):
        """Connect override substitutes the version in the manifest URL."""
        patch_requests_get.return_value.head.return_value.ok = True
        override = "2025.04.0-dev+5-gabcdef1234"
        result = get_product_artifact_by_channel(
            ProductEnum.CONNECT,
            ReleaseChannelEnum.DAILY,
            SUPPORTED_OS["ubuntu"]["24"],
            version_override=override,
        )
        assert result.version == override
        assert "2025.04.0-dev%2B5-gabcdef1234" in str(result.download_url)
        assert result.channel_latest is False

    def test_workbench_daily_override_substitutes_url(self, patch_requests_get):
        """Workbench override substitutes the version in the manifest URL."""
        patch_requests_get.return_value.head.return_value.ok = True
        override = "2025.04.0-daily+300.pro3"
        result = get_product_artifact_by_channel(
            ProductEnum.WORKBENCH,
            ReleaseChannelEnum.DAILY,
            SUPPORTED_OS["ubuntu"]["24"],
            version_override=override,
        )
        assert result.version == override
        assert "2025.04.0-daily-300.pro3" in str(result.download_url)
        assert result.channel_latest is False

    def test_ppm_channel_latest_true_when_override_equals_head(self, mocker):
        """channel_latest is True when the override exactly matches the channel head."""
        from test.config.conftest import patch_testdata_response

        mock_session = mocker.patch("posit_bakery.config.image.posit_product.main.cached_session")
        mock_session.return_value.get.side_effect = patch_testdata_response
        mock_session.return_value.head.return_value.ok = True

        # PPM daily fixture head is "2026.02.0-dev+89-ga1b2c3d4e5"
        override = "2026.02.0-dev+89-ga1b2c3d4e5"
        result = get_product_artifact_by_channel(
            ProductEnum.PACKAGE_MANAGER,
            ReleaseChannelEnum.DAILY,
            SUPPORTED_OS["ubuntu"]["24"],
            version_override=override,
        )
        assert result.channel_latest is True

    def test_connect_channel_latest_true_when_override_equals_head(self, patch_requests_get):
        """channel_latest is True when the override matches the Connect manifest version."""
        patch_requests_get.return_value.head.return_value.ok = True
        # Connect daily fixture version is "2025.04.0-dev+10-gbe0a4a3d31"
        override = "2025.04.0-dev+10-gbe0a4a3d31"
        result = get_product_artifact_by_channel(
            ProductEnum.CONNECT,
            ReleaseChannelEnum.DAILY,
            SUPPORTED_OS["ubuntu"]["24"],
            version_override=override,
        )
        assert result.channel_latest is True
        assert result.version == override

    def test_version_substitution_error_when_version_not_in_url(self, mocker):
        """VersionSubstitutionError raised when the manifest URL contains no substitutable token."""
        from test.config.conftest import patch_testdata_response

        mock_session = mocker.patch("posit_bakery.config.image.posit_product.main.cached_session")
        mock_response = mocker.MagicMock()
        # URL deliberately omits the version — no substitution is possible under any transform.
        mock_response.json.return_value = {
            "packages": [
                {
                    "platform": "ubuntu24/amd64",
                    "version": "2025.04.0-dev+10-gbe0a4a3d31",
                    "url": "https://cdn.posit.co/connect/opaque-path/artifact.deb",
                }
            ]
        }
        mock_session.return_value.get.return_value = mock_response

        with pytest.raises(VersionSubstitutionError):
            get_product_artifact_by_channel(
                ProductEnum.CONNECT,
                ReleaseChannelEnum.DAILY,
                SUPPORTED_OS["ubuntu"]["24"],
                version_override="2025.04.0-dev+5-gabcdef1234",
            )

    def test_artifact_not_available_raises(self, patch_requests_get):
        """A 404 HEAD on the substituted URL raises ArtifactNotAvailableError."""
        patch_requests_get.return_value.head.return_value.ok = False
        patch_requests_get.return_value.head.return_value.status_code = 404

        with pytest.raises(ArtifactNotAvailableError):
            get_product_artifact_by_channel(
                ProductEnum.CONNECT,
                ReleaseChannelEnum.DAILY,
                SUPPORTED_OS["ubuntu"]["24"],
                version_override="2025.04.0-dev+5-gabcdef1234",
            )

    def test_no_override_scheduled_path_unchanged(self, patch_requests_get):
        """With version_override=None, behavior is identical to before this change."""
        result = get_product_artifact_by_channel(
            ProductEnum.PACKAGE_MANAGER,
            ReleaseChannelEnum.DAILY,
            SUPPORTED_OS["ubuntu"]["24"],
        )
        assert result.version is not None
        assert result.download_url is not None
        assert result.channel_latest is True
