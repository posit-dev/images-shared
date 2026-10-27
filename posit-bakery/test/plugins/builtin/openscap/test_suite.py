import json
import shutil
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from posit_bakery.plugins.builtin.openscap.command import OS_RELEASE_SCRIPT, StrategyEnum
from posit_bakery.plugins.builtin.openscap.options import FailOnEnum, OpenSCAPOptions, OutputFormatEnum
from posit_bakery.plugins.builtin.openscap.suite import OpenSCAPSuite, resolve_options

pytestmark = [pytest.mark.unit, pytest.mark.openscap]

TESTDATA = Path(__file__).parent / "testdata"
SUITE = "posit_bakery.plugins.builtin.openscap.suite"
UBUNTU_2204 = textwrap.dedent("""\
    NAME="Ubuntu"
    VERSION="22.04.5 LTS (Jammy Jellyfish)"
    ID=ubuntu
    VERSION_ID="22.04"
    """)


def docker_stub(os_release: str = UBUNTU_2204, scan_rc: int = 2, write_results: bool = True):
    """Mimic the scanner container: answer the os-release probe and drop oscap artifacts into /out."""
    calls = []

    def _run(cmd, *_args, **_kwargs):
        calls.append(cmd)
        p = MagicMock(returncode=0, stdout=b"", stderr=b"")
        if OS_RELEASE_SCRIPT in cmd:
            p.stdout = os_release
            return p
        out = Path(next(v.split(":")[0] for v in cmd if isinstance(v, str) and v.endswith(":/out")))
        if write_results:
            for src, name in (
                ("xccdf-results.xml", "results.xml"),
                ("arf.xml", "arf.xml"),
                ("fix-script.txt", "fix.sh"),
            ):
                shutil.copyfile(TESTDATA / src, out / name)
            (out / "report.html").write_text("<html/>")
        p.returncode = scan_rc
        return p

    return _run, calls


def run_suite(tmp_path, target, stub, **kwargs):
    with (
        patch(f"{SUITE}.ensure_scanner_image"),
        patch(f"{SUITE}.resolve_strategy", return_value=StrategyEnum.IMAGE_MOUNT),
        patch(f"{SUITE}.datastream_for", side_effect=lambda product, version: TESTDATA / "ds.xml"),
        patch(f"{SUITE}.subprocess.run", side_effect=stub),
    ):
        return OpenSCAPSuite(tmp_path, [target], **kwargs).run()[0]


def test_resolve_options_precedence():
    yaml = OpenSCAPOptions(profile="cis_level2_server", failOn="high")
    resolved = resolve_options({"profile": "cis_level1_workstation", "fail_on": None}, yaml)
    assert resolved.profile == "cis_level1_workstation"
    assert resolved.fail_on == FailOnEnum.HIGH
    assert resolved.tailoring == "builtin:container"
    assert resolved.formats == [OutputFormatEnum.TABLE, OutputFormatEnum.JSON, OutputFormatEnum.HTML]


def test_scan_ok_writes_outputs(tmp_path, basic_standard_image_target):
    stub, calls = docker_stub()
    outcome = run_suite(tmp_path, basic_standard_image_target, stub, formats=list(OutputFormatEnum))
    assert outcome.status == "OK", outcome.error

    out_dir = tmp_path / "results" / "openscap" / basic_standard_image_target.image_name
    uid = basic_standard_image_target.uid
    for suffix in ("summary.json", "summary.md", "report.html", "results.xml", "arf.xml", "fix.sh"):
        assert (out_dir / f"{uid}.{suffix}").is_file(), suffix
    summary = json.loads((out_dir / f"{uid}.summary.json").read_text())
    assert summary["status"] == "OK"
    assert summary["profile"].endswith("cis_level1_server_bakery_container")

    scan_cmd = calls[-1]
    assert "--tailoring-file" in scan_cmd
    assert any(a.startswith("type=image,source=") for a in scan_cmd)


def test_gate_breach(tmp_path, basic_standard_image_target):
    stub, _ = docker_stub()
    outcome = run_suite(tmp_path, basic_standard_image_target, stub, fail_on=FailOnEnum.HIGH)
    assert outcome.status == "BREACH"
    assert outcome.error.exit_code == 2


def test_tailoring_none_scans_profile_directly(tmp_path, basic_standard_image_target):
    stub, calls = docker_stub()
    run_suite(tmp_path, basic_standard_image_target, stub, tailoring="none")
    assert "--tailoring-file" not in calls[-1]
    assert "xccdf_org.ssgproject.content_profile_cis_level1_server" in calls[-1]


def test_unsupported_os_is_skipped(tmp_path, basic_standard_image_target):
    stub, calls = docker_stub(os_release='ID=alpine\nVERSION_ID=3.20.0\nPRETTY_NAME="Alpine Linux v3.20"\n')
    outcome = run_suite(tmp_path, basic_standard_image_target, stub)
    assert outcome.status == "SKIPPED"
    assert "Alpine" in outcome.result.reason
    assert len(calls) == 1


def test_missing_profile_is_skipped(tmp_path, basic_standard_image_target):
    stub, _ = docker_stub()
    outcome = run_suite(tmp_path, basic_standard_image_target, stub, profile="stig")
    assert outcome.status == "SKIPPED"


def test_oscap_error_is_error(tmp_path, basic_standard_image_target):
    stub, _ = docker_stub(scan_rc=1, write_results=False)
    outcome = run_suite(tmp_path, basic_standard_image_target, stub)
    assert outcome.status == "ERROR"
    assert outcome.error.metadata["oscap_exit_code"] == 1


def test_validation_failure_is_error(tmp_path, basic_standard_image_target):
    # The image claims to be Ubuntu 24.04 but the ARF reports 22.04: the scan did not see the target rootfs.
    stub, _ = docker_stub(os_release=UBUNTU_2204.replace("22.04", "24.04"))
    with patch(f"{SUITE}.product_for", return_value="ubuntu2204"):
        outcome = run_suite(tmp_path, basic_standard_image_target, stub)
    assert outcome.status == "ERROR"
    assert "system_info" in outcome.error.message
