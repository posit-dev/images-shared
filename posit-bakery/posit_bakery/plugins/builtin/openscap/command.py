"""Docker command builders for the OpenSCAP scanner container."""

import hashlib
import os
import subprocess
from enum import Enum
from pathlib import Path

from posit_bakery.plugins.builtin.openscap.errors import BakeryOpenSCAPError

SCANNER_DIR = Path(__file__).parent / "scanner"
SCANNER_REPOSITORY = "bakery-openscap-scanner"
TARGET_MOUNT = "/target"
OUT_MOUNT = "/out"
DATASTREAM_MOUNT = "/content/ds.xml"

# Reads os-release through an absolute symlink without escaping into the scanner's own filesystem.
OS_RELEASE_SCRIPT = (
    'f=/target/etc/os-release; [ -e "$f" ] || [ -L "$f" ] || f=/target/usr/lib/os-release; '
    'l=$(readlink "$f"); case "$l" in /*) f="/target$l";; esac; cat "$f"'
)

# Runs the evaluation, derives a per-rule bash fix script from the results, and hands output files back to the
# invoking user so no root-owned files are left on the host. Always exits with oscap's evaluation code.
SCAN_SCRIPT = """
oscap "$@" > /out/oscap.log 2>&1
rc=$?
if [ -s /out/results.xml ]; then
  set --
  [ -f /out/tailoring.xml ] && set -- --tailoring-file /out/tailoring.xml
  oscap xccdf generate fix --fix-type bash "$@" --result-id "$FIX_RESULT_ID" --output /out/fix.sh /out/results.xml \
    >> /out/oscap.log 2>&1 || true
fi
chown -R "$OUT_OWNER" /out
exit $rc
"""


class StrategyEnum(str, Enum):
    AUTO = "auto"
    IMAGE_MOUNT = "image-mount"
    EXPORT_VOLUME = "export-volume"


def default_scanner_image() -> str:
    """Local tag for the bundled scanner image, versioned by its Containerfile contents."""
    digest = hashlib.sha256((SCANNER_DIR / "Containerfile").read_bytes()).hexdigest()[:12]
    return f"{SCANNER_REPOSITORY}:{digest}"


def ensure_scanner_image(docker: str, image: str) -> None:
    """Build the bundled scanner image if it is the default and not already present locally."""
    if image != default_scanner_image():
        return
    exists = subprocess.run([docker, "image", "inspect", image], capture_output=True).returncode == 0
    if not exists:
        cmd = [docker, "build", "-t", image, "-f", str(SCANNER_DIR / "Containerfile"), str(SCANNER_DIR)]
        p = subprocess.run(cmd, capture_output=True)
        if p.returncode != 0:
            raise BakeryOpenSCAPError("Failed to build the OpenSCAP scanner image", cmd=cmd, stdout=p.stderr)


def resolve_strategy(docker: str, strategy: StrategyEnum) -> StrategyEnum:
    """Pick image-mount when the daemon supports `--mount type=image` (Docker Engine 28+), else export-volume."""
    if strategy != StrategyEnum.AUTO:
        return strategy
    p = subprocess.run([docker, "version", "--format", "{{.Server.Version}}"], capture_output=True, text=True)
    try:
        major = int(p.stdout.strip().split(".")[0])
    except ValueError:
        return StrategyEnum.EXPORT_VOLUME
    return StrategyEnum.IMAGE_MOUNT if major >= 28 else StrategyEnum.EXPORT_VOLUME


def target_mount_args(strategy: StrategyEnum, ref: str, volume: str | None) -> list[str]:
    if strategy == StrategyEnum.IMAGE_MOUNT:
        return ["--mount", f"type=image,source={ref},target={TARGET_MOUNT}"]
    return ["-v", f"{volume}:{TARGET_MOUNT}:ro"]


def os_release_command(docker: str, scanner: str, mount_args: list[str], name: str) -> list[str]:
    return [docker, "run", "--rm", "--name", name, *mount_args, "--entrypoint", "sh", scanner, "-c", OS_RELEASE_SCRIPT]


def extract_command(docker: str, scanner: str, volume: str, name: str) -> list[str]:
    """Untar a `docker export` stream (stdin) into a volume as root, preserving ownership and dropping /.dockerenv."""
    return [docker, "run", "--rm", "-i", "--name", name, "-v", f"{volume}:{TARGET_MOUNT}", "--entrypoint", "tar",
            scanner, "-x", "--numeric-owner", "--exclude=.dockerenv", "-C", TARGET_MOUNT]  # fmt: skip


def reclaim_command(docker: str, scanner: str, out_dir: Path) -> list[str]:
    """Hand a work directory back to the invoking user after an interrupted scan left root-owned files in it."""
    return [docker, "run", "--rm", "-v", f"{out_dir}:{OUT_MOUNT}", "--entrypoint", "chown", scanner,
            "-R", f"{os.getuid()}:{os.getgid()}", OUT_MOUNT]  # fmt: skip


def fix_result_id(profile_id: str) -> str:
    return f"xccdf_org.open-scap_testresult_{profile_id}"


def scan_command(
    docker: str,
    scanner: str,
    mount_args: list[str],
    datastream: Path,
    out_dir: Path,
    profile_id: str,
    *,
    name: str,
    tailoring: bool,
    html: bool,
) -> list[str]:
    oscap_args = ["xccdf", "eval", "--profile", profile_id]
    if tailoring:
        oscap_args += ["--tailoring-file", f"{OUT_MOUNT}/tailoring.xml"]
    oscap_args += ["--results", f"{OUT_MOUNT}/results.xml", "--results-arf", f"{OUT_MOUNT}/arf.xml"]
    if html:
        oscap_args += ["--report", f"{OUT_MOUNT}/report.html"]
    oscap_args.append(DATASTREAM_MOUNT)
    return [
        docker,
        "run",
        "--rm",
        "--name",
        name,
        "--network",
        "none",
        *mount_args,
        "-v",
        f"{datastream}:{DATASTREAM_MOUNT}:ro",
        "-v",
        f"{out_dir}:{OUT_MOUNT}",
        "-e",
        f"OSCAP_PROBE_ROOT={TARGET_MOUNT}",
        "-e",
        f"OSCAP_EVALUATION_TARGET=chroot://{TARGET_MOUNT}",
        "-e",
        f"FIX_RESULT_ID={fix_result_id(profile_id)}",
        "-e",
        f"OUT_OWNER={os.getuid()}:{os.getgid()}",
        "--entrypoint",
        "sh",
        scanner,
        "-c",
        SCAN_SCRIPT,
        "sh",
        *oscap_args,
    ]
