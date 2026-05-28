"""Tests for the SociPush command wrapper."""

import pytest

from posit_bakery.plugins.builtin.soci.soci import SociPush

pytestmark = [pytest.mark.unit]


def test_default_command():
    cmd = SociPush(soci_bin="soci", image_ref="ghcr.io/posit-dev/test:soci")
    assert cmd.command == [
        "soci",
        "--namespace",
        "default",
        "push",
        "--all-platforms",
        "--existing-index",
        "warn",
        "ghcr.io/posit-dev/test:soci",
    ]


def test_with_namespace_platforms_and_skip_existing():
    cmd = SociPush(
        soci_bin="soci",
        containerd_namespace="moby",
        image_ref="reg/img:tag",
        platforms=["linux/amd64"],
        existing_index="skip",
        plain_http=True,
        max_concurrent_uploads=5,
    )
    assert cmd.command == [
        "soci",
        "--namespace",
        "moby",
        "push",
        "--platform",
        "linux/amd64",
        "--existing-index",
        "skip",
        "--plain-http",
        "--max-concurrent-uploads",
        "5",
        "reg/img:tag",
    ]
