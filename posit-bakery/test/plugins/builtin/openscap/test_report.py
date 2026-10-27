from pathlib import Path

import pytest

from posit_bakery.plugins.builtin.openscap.options import FailOnEnum
from posit_bakery.plugins.builtin.openscap.report import (
    OpenSCAPReportCollection,
    OpenSCAPScanNotRun,
    OpenSCAPScanReport,
    parse_fix_script,
    validate_scan,
)

pytestmark = [pytest.mark.unit, pytest.mark.openscap]

TESTDATA = Path(__file__).parent / "testdata"
OS_RELEASE = {"ID": "ubuntu", "VERSION_ID": "22.04", "NAME": "Ubuntu", "VERSION": "22.04.5 LTS (Jammy Jellyfish)"}


def load(**kwargs) -> OpenSCAPScanReport:
    return OpenSCAPScanReport.load(
        TESTDATA / "xccdf-results.xml",
        profile_id="xccdf_org.ssgproject.content_profile_cis_level1_server_bakery_container",
        content="ComplianceAsCode 0.1.82",
        product="ubuntu2204",
        os_release=OS_RELEASE,
        arf_file=TESTDATA / "arf.xml",
        fix_file=TESTDATA / "fix-script.txt",
        **kwargs,
    )


def test_parse_fix_script_strips_banner_and_keeps_hash_lines():
    fixes = parse_fix_script((TESTDATA / "fix-script.txt").read_text())
    assert fixes["package_telnet_removed"] == 'DEBIAN_FRONTEND=noninteractive apt-get remove -y "telnet"'
    assert "#####" in fixes["accounts_umask_etc_bashrc"]
    assert "Remediating rule" not in fixes["accounts_umask_etc_bashrc"]


class TestLoad:
    def test_counts(self):
        report = load()
        assert report.counts["pass"] == 1
        assert report.counts["fail"] == 3
        assert report.counts["unknown"] == 1
        assert report.counts["notapplicable"] == 1
        assert report.counts["notselected"] == 1

    def test_findings_ordered_and_enriched(self):
        report = load()
        assert [f.id for f in report.findings] == [
            "package_telnet_removed",
            "accounts_umask_etc_bashrc",
            "root_path_no_dot",
            "service_cron_enabled",
        ]
        telnet = report.findings[0]
        assert telnet.severity == "high"
        assert telnet.cis_refs == ["2.2.4"]
        assert telnet.title == "Remove telnet Clients"
        assert (telnet.fix_bash or "").startswith("DEBIAN_FRONTEND")
        assert report.findings[3].result == "unknown"

    def test_valid(self):
        report = load()
        assert report.valid, report.checks
        assert {c.name for c in report.checks} == {"system_info", "installed_os", "canary_rule", "evaluated_rules"}

    def test_skip_rules_mark_ignored_and_exclude_from_gate(self):
        report = load(skip_rules=["package_telnet_removed"])
        assert report.findings[0].ignored
        assert not report.breached(FailOnEnum.HIGH)
        assert report.severity_counts()["high"] == 0

    @pytest.mark.parametrize(
        "fail_on,breached",
        [
            (FailOnEnum.NONE, False),
            (FailOnEnum.HIGH, True),
            (FailOnEnum.MEDIUM, True),
            (FailOnEnum.LOW, True),
            (FailOnEnum.ANY, True),
        ],
    )
    def test_breached(self, fail_on, breached):
        assert load().breached(fail_on) is breached

    def test_breached_ignores_unknown_results(self):
        report = load(skip_rules=["package_telnet_removed", "accounts_umask_etc_bashrc", "root_path_no_dot"])
        assert not report.breached(FailOnEnum.ANY)


class TestValidation:
    def _checks(self, **overrides):
        kwargs: dict = dict(
            product="ubuntu2204",
            os_release=OS_RELEASE,
            counts={"pass": 5, "fail": 1},
            results={"file_permissions_etc_passwd": "pass"},
            arf_text=(TESTDATA / "arf.xml").read_text(),
        )
        kwargs.update(overrides)
        return {c.name: c.ok for c in validate_scan(**kwargs)}

    def test_all_ok(self):
        assert all(self._checks().values())

    def test_host_scan_detected_by_system_info(self):
        arf = (TESTDATA / "arf.xml").read_text().replace(">Ubuntu<", ">Pop!_OS<").replace("22.04.5", "24.04")
        assert self._checks(arf_text=arf)["system_info"] is False

    def test_wrong_os_detected_by_installed_os(self):
        arf = (TESTDATA / "arf.xml").read_text().replace('result="true"', 'result="false"')
        assert self._checks(arf_text=arf)["installed_os"] is False

    def test_canary_not_applicable_fails(self):
        assert self._checks(results={"file_permissions_etc_passwd": "notapplicable"})["canary_rule"] is False

    def test_nothing_evaluated_fails(self):
        assert self._checks(counts={"pass": 0, "fail": 0, "notapplicable": 300})["evaluated_rules"] is False

    def test_missing_arf_skips_arf_checks(self):
        assert set(self._checks(arf_text=None)) == {"canary_rule", "evaluated_rules"}


def test_rendering(basic_standard_image_target):
    report = load()
    data = report.to_dict(basic_standard_image_target, FailOnEnum.HIGH, "BREACH")
    assert data["gate"] == {"fail_on": "high", "breached": True}
    assert data["image"]["uid"] == basic_standard_image_target.uid
    assert data["failed_by_severity"] == {"unknown": 0, "low": 1, "medium": 1, "high": 1}

    md = report.to_markdown(basic_standard_image_target, FailOnEnum.HIGH, "BREACH")
    assert "### `package_telnet_removed` (fail, high)" in md
    assert "```bash" in md

    collection = OpenSCAPReportCollection()
    collection.add_report(basic_standard_image_target, report, "BREACH")
    assert collection.table().row_count == 1
    collection.add_report(basic_standard_image_target, OpenSCAPScanNotRun("SKIPPED", "no content", True), "SKIPPED")
    assert collection.table().row_count == 1
