import hashlib
import textwrap
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from posit_bakery.plugins.builtin.openscap import content
from posit_bakery.plugins.builtin.openscap.errors import BakeryOpenSCAPContentError

pytestmark = [pytest.mark.unit, pytest.mark.openscap]

TESTDATA = Path(__file__).parent / "testdata"
P = content.PROFILE_PREFIX


@pytest.mark.parametrize(
    "os_id,version_id,expected",
    [
        ("ubuntu", "22.04", "ubuntu2204"),
        ("ubuntu", "24.04", "ubuntu2404"),
        ("ubuntu", "26.04", "ubuntu2604"),
        ("debian", "12", "debian12"),
        ("rhel", "9.4", "rhel9"),
        ("almalinux", "9.4", "almalinux9"),
        ("sles", "15.6", "sle15"),
        ("amzn", "2023", "al2023"),
        ("alpine", "3.20.0", None),
        ("ubuntu", "", None),
    ],
)
def test_product_for(os_id, version_id, expected):
    assert content.product_for(os_id, version_id) == expected


def test_parse_os_release():
    text = textwrap.dedent("""\
        # comment
        NAME="Ubuntu"
        VERSION_ID="22.04"
        ID=ubuntu
        """)
    assert content.parse_os_release(text) == {"NAME": "Ubuntu", "VERSION_ID": "22.04", "ID": "ubuntu"}


def test_list_profiles_handles_prefixed_tags():
    assert content.list_profiles(TESTDATA / "ds.xml") == [P + "cis_level1_server", P + "cis_server_l1"]


@pytest.mark.parametrize(
    "requested,available,expected",
    [
        ("cis_level1_server", [P + "cis_level1_server"], P + "cis_level1_server"),
        (P + "cis_level1_server", [P + "cis_level1_server"], P + "cis_level1_server"),
        ("cis_level1_server", [P + "cis_server_l1"], P + "cis_server_l1"),
        ("cis_level2_server", [P + "cis"], P + "cis"),
        ("cis_level1_server", [P + "stig"], None),
    ],
)
def test_resolve_profile(requested, available, expected):
    assert content.resolve_profile(requested, available) == expected


def test_container_tailoring_deselects_only_host_rules():
    tailored_id, xml = content.container_tailoring(TESTDATA / "ds.xml", P + "cis_level1_server")
    assert tailored_id == P + "cis_level1_server" + content.CONTAINER_PROFILE_SUFFIX
    ns = {"x": "http://checklists.nist.gov/xccdf/1.2"}
    profile = ET.fromstring(xml).find("x:Profile", ns)
    assert profile is not None
    assert profile.get("extends") == P + "cis_level1_server"
    deselected = {str(s.get("idref")).removeprefix(content.RULE_PREFIX) for s in profile.findall("x:select", ns)}
    assert deselected == {"sysctl_kernel_randomize_va_space", "kernel_module_cramfs_disabled", "partition_for_tmp"}


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("BAKERY_OPENSCAP_CACHE", str(tmp_path))
    return tmp_path


def _fake_release(tmp_path: Path) -> bytes:
    zpath = tmp_path / "src.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("scap-security-guide-9.9/ssg-ubuntu2204-ds.xml", "<ds/>")
    return zpath.read_bytes()


def _mock_get(payload: bytes, checksum: str):
    def get(url, **_kwargs):
        r = MagicMock()
        r.__enter__.return_value = r
        r.iter_content.return_value = [payload]
        r.text = f"{checksum}  scap-security-guide-9.9.zip\n"
        return r

    return get


def test_release_zip_verifies_checksum_and_extracts(cache, tmp_path):
    payload = _fake_release(tmp_path)
    with patch.object(content.requests, "get", side_effect=_mock_get(payload, hashlib.sha512(payload).hexdigest())):
        ds = content.datastream_for("ubuntu2204", "9.9")
        assert ds is not None
        assert ds.read_text() == "<ds/>"
        assert content.datastream_for("debian12", "9.9") is None


def test_release_zip_checksum_mismatch(cache, tmp_path):
    payload = _fake_release(tmp_path)
    with patch.object(content.requests, "get", side_effect=_mock_get(payload, "0" * 128)):
        with pytest.raises(BakeryOpenSCAPContentError, match="Checksum mismatch"):
            content.release_zip("9.9")
    assert not (cache / "9.9" / "scap-security-guide-9.9.zip").exists()


def test_fetch_file_missing_path():
    with pytest.raises(BakeryOpenSCAPContentError):
        content.fetch_file("/nonexistent/tailoring.xml")
