"""Tests for the SociConvert command wrapper."""

import pytest

from posit_bakery.plugins.builtin.soci.soci import SociConvert

pytestmark = [pytest.mark.unit]


def test_default_non_standalone_command():
    cmd = SociConvert(
        soci_bin="soci",
        source="ghcr.io/posit-dev/test/tmp:src",
        destination="ghcr.io/posit-dev/test/tmp:src-soci",
    )
    assert cmd.command == [
        "soci",
        "--namespace",
        "default",
        "convert",
        "--all-platforms",
        "ghcr.io/posit-dev/test/tmp:src",
        "ghcr.io/posit-dev/test/tmp:src-soci",
    ]


def test_with_explicit_namespace_and_address():
    cmd = SociConvert(
        soci_bin="/opt/soci",
        containerd_address="/run/containerd/alt.sock",
        containerd_namespace="moby",
        source="src",
        destination="dst",
    )
    assert cmd.command == [
        "/opt/soci",
        "--address",
        "/run/containerd/alt.sock",
        "--namespace",
        "moby",
        "convert",
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
        "--namespace",
        "default",
        "convert",
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


def test_standalone_mode_includes_flag_and_format():
    cmd = SociConvert(
        soci_bin="soci",
        source="./img.tar",
        destination="./img-soci.tar",
        standalone=True,
        output_format="oci-archive",
    )
    assert "--standalone" in cmd.command
    assert "--format" in cmd.command
    assert "oci-archive" in cmd.command
    # namespace flag is still emitted even in standalone — soci ignores it
    # there; we keep the construction uniform.
