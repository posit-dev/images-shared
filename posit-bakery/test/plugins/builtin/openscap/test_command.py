from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from posit_bakery.plugins.builtin.openscap import command
from posit_bakery.plugins.builtin.openscap.command import StrategyEnum

pytestmark = [pytest.mark.unit, pytest.mark.openscap]


@pytest.mark.parametrize(
    "server_version,expected",
    [
        ("29.9.2", StrategyEnum.IMAGE_MOUNT),
        ("28.0.0", StrategyEnum.IMAGE_MOUNT),
        ("27.5.1", StrategyEnum.EXPORT_VOLUME),
        ("", StrategyEnum.EXPORT_VOLUME),
    ],
)
def test_resolve_strategy_auto(server_version, expected):
    with patch.object(command.subprocess, "run", return_value=MagicMock(stdout=server_version)):
        assert command.resolve_strategy("docker", StrategyEnum.AUTO) == expected


def test_resolve_strategy_explicit_skips_probe():
    with patch.object(command.subprocess, "run") as run:
        assert command.resolve_strategy("docker", StrategyEnum.EXPORT_VOLUME) == StrategyEnum.EXPORT_VOLUME
        run.assert_not_called()


def test_target_mount_args():
    assert command.target_mount_args(StrategyEnum.IMAGE_MOUNT, "img:1", None) == [
        "--mount",
        "type=image,source=img:1,target=/target",
    ]
    assert command.target_mount_args(StrategyEnum.EXPORT_VOLUME, "img:1", "vol") == ["-v", "vol:/target:ro"]


def test_scan_command():
    cmd = command.scan_command(
        "docker", "scanner:1", ["-v", "vol:/target:ro"], Path("/c/ds.xml"), Path("/w"), "PROFILE",
        name="n1", tailoring=True, html=False,
    )  # fmt: skip
    assert cmd[:5] == ["docker", "run", "--rm", "--name", "n1"]
    assert "OSCAP_PROBE_ROOT=/target" in cmd
    assert "/c/ds.xml:/content/ds.xml:ro" in cmd
    assert "/w:/out" in cmd
    assert "FIX_RESULT_ID=xccdf_org.open-scap_testresult_PROFILE" in cmd
    oscap_args = cmd[cmd.index("sh", cmd.index("-c")) + 1 :]
    assert oscap_args[:4] == ["xccdf", "eval", "--profile", "PROFILE"]
    assert "--tailoring-file" in oscap_args
    assert "--report" not in oscap_args
    assert oscap_args[-1] == "/content/ds.xml"


def test_default_scanner_image_is_content_addressed():
    assert command.default_scanner_image().startswith(command.SCANNER_REPOSITORY + ":")
