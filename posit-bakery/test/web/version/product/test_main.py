import pytest

from posit_bakery.models.manifest import SUPPORTED_OS, BuildOS
from posit_bakery.web.version.product import ProductEnum
from posit_bakery.web.version.product.main import _parse_download_json_os_identifier, _make_resolver_metadata

tag_os_dict = {_os.image_tag: _os for _os in SUPPORTED_OS}
helper_test_collection = [
    *[
        (
            tag_os_dict[_os_tag],
            product,
            {"download_json_os": "noble", "os": tag_os_dict[_os_tag], "arch_identifier": "amd64"},
        )
        for product in ProductEnum
        for _os_tag in ["debian-12", "ubuntu-24.04"]
    ],
    *[
        (
            tag_os_dict[_os_tag],
            product,
            {"download_json_os": "jammy", "os": tag_os_dict[_os_tag], "arch_identifier": "amd64"},
        )
        for product in ProductEnum
        for _os_tag in ["debian-11", "ubuntu-22.04"]
    ],
    *[
        (
            tag_os_dict[_os_tag],
            ProductEnum.CONNECT,
            {"download_json_os": "redhat8", "os": tag_os_dict[_os_tag], "arch_identifier": "x86_64"},
        )
        for _os_tag in ["almalinux-8", "rockylinux-8"]
    ],
    *[
        (
            tag_os_dict[_os_tag],
            ProductEnum.PACKAGE_MANAGER,
            {"download_json_os": "fedora28", "os": tag_os_dict[_os_tag], "arch_identifier": "x86_64"},
        )
        for _os_tag in ["almalinux-8", "rockylinux-8"]
    ],
    *[
        (
            tag_os_dict[_os_tag],
            product,
            {"download_json_os": "rhel8", "os": tag_os_dict[_os_tag], "arch_identifier": "x86_64"},
        )
        for product in [ProductEnum.WORKBENCH, ProductEnum.WORKBENCH_SESSION]
        for _os_tag in ["almalinux-8", "rockylinux-8"]
    ],
    *[
        (
            tag_os_dict[_os_tag],
            product,
            {"download_json_os": "rhel9", "os": tag_os_dict[_os_tag], "arch_identifier": "x86_64"},
        )
        for product in ProductEnum
        for _os_tag in ["almalinux-9", "rockylinux-9"]
    ],
    *[
        (
            tag_os_dict["scratch"],
            product,
            {"download_json_os": "multi", "os": tag_os_dict["scratch"], "arch_identifier": "amd64"},
        )
        for product in ProductEnum
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
