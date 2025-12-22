import pytest

from posit_bakery.config.image.build_os import SUPPORTED_OS, BuildOS
from posit_bakery.config.image.posit_product.const import ProductEnum, ReleaseStreamEnum
from posit_bakery.config.image.posit_product.main import (
    _parse_download_json_os_identifier,
    _make_resolver_metadata,
    _get_arch_identifier,
    _replace_arch_in_url,
    _is_template_based_stream,
    get_product_artifact_by_stream,
    product_release_stream_url_map,
    ARCH_PLACEHOLDER,
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


class TestGetProductArtifactByStream:
    def test_bad_product(self):
        """Test that an invalid product raises an error"""
        with pytest.raises(ValueError):
            get_product_artifact_by_stream("bad", "daily", SUPPORTED_OS["ubuntu"]["22"])

    def test_bad_stream(self):
        """Test that an invalid stream raises an error"""
        with pytest.raises(ValueError):
            get_product_artifact_by_stream("connect", "preview", SUPPORTED_OS["ubuntu"]["22"])

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
        output = get_product_artifact_by_stream(ProductEnum.CONNECT, ReleaseStreamEnum.RELEASE, _os)
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
        output = get_product_artifact_by_stream(ProductEnum.CONNECT, ReleaseStreamEnum.DAILY, _os)
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
        output = get_product_artifact_by_stream(ProductEnum.PACKAGE_MANAGER, ReleaseStreamEnum.RELEASE, _os)
        assert output.version == expected_version
        assert str(output.download_url) == expected_url

    @pytest.mark.parametrize(
        "_os,expected_version,expected_url",
        [
            pytest.param(
                SUPPORTED_OS["debian"]["12"],
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2024.11.1-3776_amd64.deb",
                id="debian-12",
            ),
            pytest.param(
                SUPPORTED_OS["debian"]["11"],
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2024.11.1-3776_amd64.deb",
                id="debian-11",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["24"],
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2024.11.1-3776_amd64.deb",
                id="ubuntu-24",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["22"],
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2024.11.1-3776_amd64.deb",
                id="ubuntu-22",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["8"],
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.1-3776.x86_64.rpm",
                id="alma-8",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["8"],
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.1-3776.x86_64.rpm",
                id="rocky-8",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["8"],
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.1-3776.x86_64.rpm",
                id="rhel-8",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["9"],
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.1-3776.x86_64.rpm",
                id="alma-9",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["9"],
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.1-3776.x86_64.rpm",
                id="rocky-9",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["9"],
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.1-3776.x86_64.rpm",
                id="rhel-9",
            ),
        ],
    )
    def test_package_manager_preview(self, patch_requests_get, _os: BuildOS, expected_version: str, expected_url: str):
        """Test that the correct URL is returned for a release version of PPM Preview"""
        output = get_product_artifact_by_stream(ProductEnum.PACKAGE_MANAGER, ReleaseStreamEnum.PREVIEW, _os)
        assert output.version == expected_version
        assert str(output.download_url) == expected_url

    @pytest.mark.parametrize(
        "_os,expected_version,expected_url",
        [
            pytest.param(
                SUPPORTED_OS["debian"]["12"],
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2024.11.2-9_amd64.deb",
                id="debian-12",
            ),
            pytest.param(
                SUPPORTED_OS["debian"]["11"],
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2024.11.2-9_amd64.deb",
                id="debian-11",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["24"],
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2024.11.2-9_amd64.deb",
                id="ubuntu-24",
            ),
            pytest.param(
                SUPPORTED_OS["ubuntu"]["22"],
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2024.11.2-9_amd64.deb",
                id="ubuntu-22",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["8"],
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.2-9.x86_64.rpm",
                id="alma-8",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["8"],
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.2-9.x86_64.rpm",
                id="rocky-8",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["8"],
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.2-9.x86_64.rpm",
                id="rhel-8",
            ),
            pytest.param(
                SUPPORTED_OS["alma"]["9"],
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.2-9.x86_64.rpm",
                id="alma-9",
            ),
            pytest.param(
                SUPPORTED_OS["rocky"]["9"],
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.2-9.x86_64.rpm",
                id="rocky-9",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["9"],
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.2-9.x86_64.rpm",
                id="rhel-9",
            ),
        ],
    )
    def test_package_manager_daily(self, patch_requests_get, _os: BuildOS, expected_version: str, expected_url: str):
        """Test that the correct URL is returned for a release version of PPM Daily"""
        output = get_product_artifact_by_stream(ProductEnum.PACKAGE_MANAGER, ReleaseStreamEnum.DAILY, _os)
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
        output = get_product_artifact_by_stream(ProductEnum.WORKBENCH, ReleaseStreamEnum.RELEASE, _os)
        assert output.version == expected_version
        assert str(output.download_url) == expected_url

        output = get_product_artifact_by_stream(ProductEnum.WORKBENCH_SESSION, ReleaseStreamEnum.RELEASE, _os)
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
        output = get_product_artifact_by_stream(ProductEnum.WORKBENCH, ReleaseStreamEnum.DAILY, _os)
        assert output.version == expected_version
        assert str(output.download_url) == expected_url

        output = get_product_artifact_by_stream(ProductEnum.WORKBENCH_SESSION, ReleaseStreamEnum.DAILY, _os)
        assert output.version == expected_version
        assert str(output.download_url) == expected_session_url


class TestArchPlaceholder:
    """Tests for architecture placeholder functionality."""

    def test_get_arch_identifier_debian_default(self):
        """Test that Debian-like OS returns 'amd64' by default."""
        _os = SUPPORTED_OS["ubuntu"]["22"]
        assert _get_arch_identifier(_os) == "amd64"

    def test_get_arch_identifier_rhel_default(self):
        """Test that RHEL-like OS returns 'x86_64' by default."""
        _os = SUPPORTED_OS["rhel"]["9"]
        assert _get_arch_identifier(_os) == "x86_64"

    def test_get_arch_identifier_with_placeholder(self):
        """Test that use_placeholder=True returns the placeholder constant."""
        _os = SUPPORTED_OS["ubuntu"]["22"]
        assert _get_arch_identifier(_os, use_placeholder=True) == ARCH_PLACEHOLDER

        _os = SUPPORTED_OS["rhel"]["9"]
        assert _get_arch_identifier(_os, use_placeholder=True) == ARCH_PLACEHOLDER

    def test_make_resolver_metadata_with_placeholder(self):
        """Test that metadata contains placeholder when use_arch_placeholder=True."""
        _os = SUPPORTED_OS["ubuntu"]["22"]
        meta = _make_resolver_metadata(_os, ProductEnum.CONNECT, use_arch_placeholder=True)
        assert meta["arch_identifier"] == ARCH_PLACEHOLDER

    def test_replace_arch_in_url_debian(self):
        """Test URL arch replacement for Debian-based systems."""
        _os = SUPPORTED_OS["ubuntu"]["22"]
        url = "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_1.0.0_amd64.deb"
        result = _replace_arch_in_url(url, _os)
        assert "amd64" not in result
        assert ARCH_PLACEHOLDER in result
        assert (
            result
            == f"https://cdn.posit.co/package-manager/deb/{ARCH_PLACEHOLDER}/rstudio-pm_1.0.0_{ARCH_PLACEHOLDER}.deb"
        )

    def test_replace_arch_in_url_debian_arm64(self):
        """Test URL arch replacement for Debian-based ARM systems."""
        _os = SUPPORTED_OS["ubuntu"]["22"]
        url = "https://cdn.posit.co/package-manager/deb/arm64/rstudio-pm_1.0.0_arm64.deb"
        result = _replace_arch_in_url(url, _os)
        assert "arm64" not in result
        assert ARCH_PLACEHOLDER in result

    def test_replace_arch_in_url_rhel(self):
        """Test URL arch replacement for RHEL-based systems."""
        _os = SUPPORTED_OS["rhel"]["9"]
        url = "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-1.0.0.x86_64.rpm"
        result = _replace_arch_in_url(url, _os)
        assert "x86_64" not in result
        assert ARCH_PLACEHOLDER in result

    def test_replace_arch_in_url_rhel_aarch64(self):
        """Test URL arch replacement for RHEL-based ARM systems."""
        _os = SUPPORTED_OS["rhel"]["9"]
        url = "https://cdn.posit.co/package-manager/rpm/arm64/rstudio-pm-1.0.0.aarch64.rpm"
        result = _replace_arch_in_url(url, _os)
        assert "aarch64" not in result
        # Note: arm64 in path should remain (only x86_64 and aarch64 are replaced for RHEL)
        assert ARCH_PLACEHOLDER in result

    def test_is_template_based_stream_ppm_preview(self):
        """Test that Package Manager preview/daily are identified as template-based."""
        stream_path = product_release_stream_url_map[ProductEnum.PACKAGE_MANAGER][ReleaseStreamEnum.PREVIEW]
        assert _is_template_based_stream(stream_path) is True

        stream_path = product_release_stream_url_map[ProductEnum.PACKAGE_MANAGER][ReleaseStreamEnum.DAILY]
        assert _is_template_based_stream(stream_path) is True

    def test_is_template_based_stream_ppm_release(self):
        """Test that Package Manager release is NOT template-based (uses JSON)."""
        stream_path = product_release_stream_url_map[ProductEnum.PACKAGE_MANAGER][ReleaseStreamEnum.RELEASE]
        assert _is_template_based_stream(stream_path) is False

    def test_is_template_based_stream_connect(self):
        """Test that Connect streams are NOT template-based (uses JSON)."""
        stream_path = product_release_stream_url_map[ProductEnum.CONNECT][ReleaseStreamEnum.RELEASE]
        assert _is_template_based_stream(stream_path) is False

        stream_path = product_release_stream_url_map[ProductEnum.CONNECT][ReleaseStreamEnum.DAILY]
        assert _is_template_based_stream(stream_path) is False

    @pytest.mark.parametrize(
        "_os,expected_url_pattern",
        [
            pytest.param(
                SUPPORTED_OS["ubuntu"]["22"],
                f"https://cdn.posit.co/package-manager/deb/{ARCH_PLACEHOLDER}/rstudio-pm_",
                id="ubuntu-22",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["9"],
                f"https://cdn.posit.co/package-manager/rpm/{ARCH_PLACEHOLDER}/rstudio-pm-",
                id="rhel-9",
            ),
        ],
    )
    def test_ppm_preview_with_placeholder(self, patch_requests_get, _os: BuildOS, expected_url_pattern: str):
        """Test Package Manager preview with arch placeholder."""
        output = get_product_artifact_by_stream(
            ProductEnum.PACKAGE_MANAGER, ReleaseStreamEnum.PREVIEW, _os, use_arch_placeholder=True
        )
        assert expected_url_pattern in str(output.download_url)
        assert ARCH_PLACEHOLDER in str(output.download_url)
        # Version should still be resolved correctly
        assert output.version == "2024.11.1-3776"

    @pytest.mark.parametrize(
        "_os,expected_url_pattern",
        [
            pytest.param(
                SUPPORTED_OS["ubuntu"]["22"],
                f"https://cdn.posit.co/package-manager/deb/{ARCH_PLACEHOLDER}/rstudio-pm_",
                id="ubuntu-22",
            ),
            pytest.param(
                SUPPORTED_OS["rhel"]["9"],
                f"https://cdn.posit.co/package-manager/rpm/{ARCH_PLACEHOLDER}/rstudio-pm-",
                id="rhel-9",
            ),
        ],
    )
    def test_ppm_daily_with_placeholder(self, patch_requests_get, _os: BuildOS, expected_url_pattern: str):
        """Test Package Manager daily with arch placeholder."""
        output = get_product_artifact_by_stream(
            ProductEnum.PACKAGE_MANAGER, ReleaseStreamEnum.DAILY, _os, use_arch_placeholder=True
        )
        assert expected_url_pattern in str(output.download_url)
        assert ARCH_PLACEHOLDER in str(output.download_url)
        # Version should still be resolved correctly
        assert output.version == "2024.11.2-9"

    @pytest.mark.parametrize(
        "_os",
        [
            pytest.param(SUPPORTED_OS["ubuntu"]["22"], id="ubuntu-22"),
            pytest.param(SUPPORTED_OS["rhel"]["9"], id="rhel-9"),
        ],
    )
    def test_connect_release_with_placeholder(self, patch_requests_get, _os: BuildOS):
        """Test Connect release with arch placeholder (JSON-based stream)."""
        output = get_product_artifact_by_stream(
            ProductEnum.CONNECT, ReleaseStreamEnum.RELEASE, _os, use_arch_placeholder=True
        )
        assert ARCH_PLACEHOLDER in str(output.download_url)
        # Version should still be resolved correctly
        assert output.version == "2025.03.0"

    @pytest.mark.parametrize(
        "_os",
        [
            pytest.param(SUPPORTED_OS["ubuntu"]["22"], id="ubuntu-22"),
            pytest.param(SUPPORTED_OS["rhel"]["9"], id="rhel-9"),
        ],
    )
    def test_workbench_daily_with_placeholder(self, patch_requests_get, _os: BuildOS):
        """Test Workbench daily with arch placeholder (JSON-based stream)."""
        output = get_product_artifact_by_stream(
            ProductEnum.WORKBENCH, ReleaseStreamEnum.DAILY, _os, use_arch_placeholder=True
        )
        assert ARCH_PLACEHOLDER in str(output.download_url)
        # Version should still be resolved correctly
        assert output.version == "2025.04.0-daily+404.pro4"
