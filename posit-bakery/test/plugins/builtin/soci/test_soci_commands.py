"""Tests for SociCommand sudo prefixing."""

import pytest

from posit_bakery.plugins.builtin.soci.soci import SociConvert, SociPush

pytestmark = [pytest.mark.unit]


def test_convert_sudo_prepends_prefix():
    cmd = SociConvert(soci_bin="soci", source="src", destination="dst", sudo=True)
    assert cmd.command[:3] == ["sudo", "-n", "soci"]


def test_convert_no_sudo_by_default():
    cmd = SociConvert(soci_bin="soci", source="src", destination="dst")
    assert cmd.command[0] == "soci"
    assert "sudo" not in cmd.command


def test_push_sudo_prepends_prefix():
    cmd = SociPush(soci_bin="soci", image_ref="reg/img:tag", sudo=True)
    assert cmd.command[:3] == ["sudo", "-n", "soci"]


def test_push_no_sudo_by_default():
    cmd = SociPush(soci_bin="soci", image_ref="reg/img:tag")
    assert cmd.command[0] == "soci"
    assert "sudo" not in cmd.command
