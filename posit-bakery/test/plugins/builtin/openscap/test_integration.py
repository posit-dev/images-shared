"""Live scans with the real scanner image and SSG content.

Opt-in (BAKERY_TEST_OPENSCAP=1): it downloads ~180 MB of CIS-titled content, which is kept out of public CI.
"""

import os
import subprocess
from unittest.mock import patch

import pytest

from posit_bakery.plugins.builtin.openscap.command import StrategyEnum
from posit_bakery.plugins.builtin.openscap.suite import OpenSCAPSuite

pytestmark = [
    pytest.mark.slow,
    pytest.mark.image_build,
    pytest.mark.openscap,
    pytest.mark.skipif(not os.environ.get("BAKERY_TEST_OPENSCAP"), reason="set BAKERY_TEST_OPENSCAP=1 to run"),
]

WEAKENED = "bakery-openscap-test:weakened"


@pytest.fixture(scope="module")
def weakened_image():
    containerfile = (
        "FROM docker.io/library/ubuntu:22.04\n"
        "RUN apt-get update && apt-get install -y --no-install-recommends telnet && rm -rf /var/lib/apt/lists/*\n"
        "RUN chmod 0777 /etc/passwd\n"
    )
    subprocess.run(["docker", "build", "-t", WEAKENED, "-"], input=containerfile.encode(), check=True)
    yield WEAKENED
    subprocess.run(["docker", "rmi", "-f", WEAKENED], capture_output=True)


def scan(tmp_path, target, image, strategy):
    with patch.object(type(target), "ref", lambda self, *a, **k: image):
        return OpenSCAPSuite(tmp_path, [target], strategy=strategy).run()[0]


@pytest.mark.parametrize("strategy", [StrategyEnum.AUTO, StrategyEnum.EXPORT_VOLUME])
def test_scan_detects_image_changes(tmp_path, basic_standard_image_target, weakened_image, strategy):
    subprocess.run(["docker", "pull", "-q", "docker.io/library/ubuntu:22.04"], check=True, capture_output=True)
    base = scan(tmp_path / "base", basic_standard_image_target, "docker.io/library/ubuntu:22.04", strategy)
    weak = scan(tmp_path / "weak", basic_standard_image_target, weakened_image, strategy)
    assert base.status == weak.status == "OK", (base.error, weak.error)

    def failing(outcome):
        return {f.id for f in outcome.result.findings if f.result == "fail"}

    for rule in ("package_telnet_removed", "file_permissions_etc_passwd"):
        assert rule not in failing(base)
        assert rule in failing(weak)
    # Running as root in the scanner preserves ownership, so ownership rules must not fail on a stock image.
    assert not {r for r in failing(base) if r.startswith(("file_owner", "file_groupowner"))}
