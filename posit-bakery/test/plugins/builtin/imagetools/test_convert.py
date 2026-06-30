"""Tests for the SociConvert command wrapper."""

import pytest

from posit_bakery.plugins.builtin.imagetools.soci import SociConvert

pytestmark = [pytest.mark.unit]


def test_default_command():
    cmd = SociConvert(
        soci_bin="soci",
        source="./img.tar",
        destination="./img-soci.tar",
    )
    assert cmd.command == [
        "soci",
        "convert",
        "--standalone",
        "--format",
        "oci-archive",
        "--all-platforms",
        "./img.tar",
        "./img-soci.tar",
    ]


def test_oci_dir_output_format():
    cmd = SociConvert(
        soci_bin="/opt/soci",
        source="src",
        destination="dst",
        output_format="oci-dir",
    )
    assert cmd.command == [
        "/opt/soci",
        "convert",
        "--standalone",
        "--format",
        "oci-dir",
        "--all-platforms",
        "src",
        "dst",
    ]


def test_with_specific_platforms_and_options():
    cmd = SociConvert(
        soci_bin="soci",
        source="src",
        destination="dst",
        platforms=["linux/amd64", "linux/arm64"],
        span_size=4 * 1024 * 1024,
        min_layer_size=10 * 1024 * 1024,
        prefetch_files=["/a", "/b"],
        optimizations=["xattr"],
        force=True,
    )
    assert cmd.command == [
        "soci",
        "convert",
        "--standalone",
        "--format",
        "oci-archive",
        "--platform",
        "linux/amd64",
        "--platform",
        "linux/arm64",
        "--span-size",
        "4194304",
        "--min-layer-size",
        "10485760",
        "--prefetch-file",
        "/a",
        "--prefetch-file",
        "/b",
        "--optimizations",
        "xattr",
        "--force",
        "src",
        "dst",
    ]
