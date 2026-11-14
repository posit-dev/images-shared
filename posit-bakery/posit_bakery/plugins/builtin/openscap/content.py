"""SCAP content resolution: ComplianceAsCode release download/caching, OS -> product mapping,
profile resolution and the built-in container tailoring."""

import hashlib
import logging
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import requests

from posit_bakery.plugins.builtin.openscap.errors import BakeryOpenSCAPContentError

log = logging.getLogger(__name__)

# renovate: datasource=github-releases depName=ComplianceAsCode/content extractVersion=^v(?<version>.*)$
DEFAULT_CONTENT_VERSION = "0.1.82"
RELEASE_URL = (
    "https://github.com/ComplianceAsCode/content/releases/download/v{version}/scap-security-guide-{version}.zip"
)
DOWNLOAD_TIMEOUT = 300

PROFILE_PREFIX = "xccdf_org.ssgproject.content_profile_"
RULE_PREFIX = "xccdf_org.ssgproject.content_rule_"
CONTAINER_PROFILE_SUFFIX = "_bakery_container"

# Products name some CIS profiles differently (e.g. RHEL); tried in order when the requested name is absent.
PROFILE_ALIASES = {
    "cis_level1_server": ["cis_server_l1"],
    "cis_level2_server": ["cis"],
    "cis_level1_workstation": ["cis_workstation_l1"],
    "cis_level2_workstation": ["cis_workstation_l2"],
}

# Rule families that evaluate host/kernel/boot state rather than image contents. They are deselected by the
# built-in container tailoring. Derived from the offline-probe coverage spike (see docs/openscap-plugin-spec.md).
HOST_ONLY_RULE_PATTERN = re.compile(
    r"^(sysctl_|kernel_module_|kernel_|grub2_|grub_|zipl_|partition_for_|mount_option_|audit_rules_|auditd_"
    r"|service_auditd|package_audit|aide_|package_aide|apparmor|package_apparmor|coredump_|service_(chronyd|timesyncd|ntp)"
    r"|ntp_|chronyd_|timesyncd|package_(chrony|systemd-timesyncd)|systemd_journal_upload|service_systemd-journal"
    r"|socket_systemd)"
)

_PROFILE_ID_RE = re.compile(r'<(?:[\w.-]+:)?Profile\b[^>]*?\sid="([^"]+)"')
_RULE_ID_RE = re.compile(r'<(?:[\w.-]+:)?Rule\b[^>]*?\sid="(' + re.escape(RULE_PREFIX) + r'[^"]+)"')


def cache_root() -> Path:
    """Content cache directory, overridable with BAKERY_OPENSCAP_CACHE."""
    if os.environ.get("BAKERY_OPENSCAP_CACHE"):
        return Path(os.environ["BAKERY_OPENSCAP_CACHE"])
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "bakery" / "openscap"


def product_for(os_id: str, version_id: str) -> str | None:
    """Map /etc/os-release ID and VERSION_ID to a ComplianceAsCode product ID, e.g. ubuntu 22.04 -> ubuntu2204."""
    os_id = os_id.lower()
    major = version_id.split(".")[0]
    if not version_id:
        return None
    if os_id == "ubuntu":
        return "ubuntu" + version_id.replace(".", "")
    if os_id in ("debian", "rhel", "ol", "almalinux"):
        return os_id + major
    if os_id == "alma":
        return "almalinux" + major
    if os_id in ("sles", "sled", "sle"):
        return "sle" + major
    if os_id == "amzn" and major == "2023":
        return "al2023"
    if os_id == "fedora":
        return "fedora"
    return None


def parse_os_release(text: str) -> dict[str, str]:
    """Parse an os-release file into a dict."""
    result = {}
    for line in text.splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _temp_path(dest: Path) -> Path:
    """A unique sibling path, so concurrent writers never share or expose partial files under `dest`."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.", suffix=".part")
    os.close(fd)
    return Path(name)


def _download(url: str, dest: Path) -> None:
    """Download `url` to a unique temp file next to `dest`; the caller verifies and publishes it."""
    log.info(f"Downloading {url}")
    try:
        with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
    except (requests.RequestException, OSError) as e:
        raise BakeryOpenSCAPContentError(f"Failed to download {url}: {e}") from e


def _sha512(path: Path) -> str:
    h = hashlib.sha512()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError as e:
        raise BakeryOpenSCAPContentError(f"Failed to read {path}: {e}") from e
    return h.hexdigest()


def release_zip(version: str = DEFAULT_CONTENT_VERSION) -> Path:
    """Download (once) and sha512-verify the SCAP Security Guide release zip, returning its cached path.

    The zip only appears at its cached path after verification, so an interrupted run never leaves an
    unverified archive that a later run would trust.
    """
    dest = cache_root() / version / f"scap-security-guide-{version}.zip"
    if dest.is_file():
        return dest
    url = RELEASE_URL.format(version=version)
    tmp = _temp_path(dest)
    try:
        try:
            r = requests.get(url + ".sha512", timeout=60)
            r.raise_for_status()
            expected = r.text.split()[0].lower()
        except (requests.RequestException, IndexError) as e:
            raise BakeryOpenSCAPContentError(f"Failed to fetch checksum for {url}: {e}") from e
        _download(url, tmp)
        if _sha512(tmp) != expected:
            raise BakeryOpenSCAPContentError(f"Checksum mismatch for {url}")
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)
    return dest


def datastream_for(product: str, version: str = DEFAULT_CONTENT_VERSION) -> Path | None:
    """Return the cached `ssg-<product>-ds.xml` for a release, extracting it if needed. None if not shipped."""
    dest = cache_root() / version / f"ssg-{product}-ds.xml"
    if dest.is_file():
        return dest
    member = f"scap-security-guide-{version}/ssg-{product}-ds.xml"
    archive = release_zip(version)
    tmp = _temp_path(dest)
    try:
        with zipfile.ZipFile(archive) as z:
            if member not in z.namelist():
                return None
            with z.open(member) as src, open(tmp, "wb") as out:
                shutil.copyfileobj(src, out)
        tmp.replace(dest)
    except (OSError, zipfile.BadZipFile) as e:
        raise BakeryOpenSCAPContentError(f"Failed to extract {member} from {archive}: {e}") from e
    finally:
        tmp.unlink(missing_ok=True)
    return dest


def is_url(location: str) -> bool:
    return location.startswith(("http://", "https://"))


def fetch_file(location: str, base_dir: Path | None = None) -> Path:
    """Resolve a path (relative paths against `base_dir`) or URL to a local file, caching URLs by hash."""
    if is_url(location):
        dest = cache_root() / "url" / hashlib.sha256(location.encode()).hexdigest()[:16] / "content.xml"
        if not dest.is_file():
            tmp = _temp_path(dest)
            try:
                _download(location, tmp)
                tmp.replace(dest)
            finally:
                tmp.unlink(missing_ok=True)
        return dest
    path = Path(location).expanduser()
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    if not path.is_file():
        raise BakeryOpenSCAPContentError(f"File not found: {path}")
    return path.resolve()


def list_profiles(datastream: Path) -> list[str]:
    """Return the unique profile IDs defined in a datastream."""
    return list(dict.fromkeys(_PROFILE_ID_RE.findall(datastream.read_text(encoding="utf-8"))))


def resolve_profile(profile: str, available: list[str]) -> str | None:
    """Resolve a short or full profile name against the profiles available in a datastream."""
    if profile in available:
        return profile
    short = profile.removeprefix(PROFILE_PREFIX)
    for candidate in [short, *PROFILE_ALIASES.get(short, [])]:
        if PROFILE_PREFIX + candidate in available:
            return PROFILE_PREFIX + candidate
    return None


def container_tailoring(datastream: Path, profile_id: str) -> tuple[str, str]:
    """Build an XCCDF 1.2 tailoring that extends `profile_id` and deselects host/kernel-only rules.

    :return: (tailored profile ID, tailoring XML)
    """
    rules = dict.fromkeys(_RULE_ID_RE.findall(datastream.read_text(encoding="utf-8")))
    host_rules = [r for r in rules if HOST_ONLY_RULE_PATTERN.match(r.removeprefix(RULE_PREFIX))]
    tailored_id = profile_id + CONTAINER_PROFILE_SUFFIX
    selects = "\n".join(f'    <xccdf:select idref="{escape(r)}" selected="false"/>' for r in host_rules)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<xccdf:Tailoring xmlns:xccdf="http://checklists.nist.gov/xccdf/1.2" id="xccdf_posit.bakery_tailoring_container">
  <xccdf:benchmark href="{escape(datastream.name)}"/>
  <xccdf:version time="2000-01-01T00:00:00">1</xccdf:version>
  <xccdf:Profile id="{escape(tailored_id)}" extends="{escape(profile_id)}">
    <xccdf:title>{escape(profile_id.removeprefix(PROFILE_PREFIX))} - container image (Bakery)</xccdf:title>
{selects}
  </xccdf:Profile>
</xccdf:Tailoring>
"""
    return tailored_id, xml
