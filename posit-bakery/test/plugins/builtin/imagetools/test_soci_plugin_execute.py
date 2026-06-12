"""ImageToolsPlugin.execute() on the SOCI phase subset (the `bakery soci convert` path).

Detailed gating/sequencing is covered in test_publish.py; here we exercise the plugin's
dry-run integration (parallel executor, bin resolution) without requiring real tools.
"""

from unittest.mock import MagicMock, patch

import pytest

import posit_bakery.util as util
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.imagetools import ImageToolsPlugin
from posit_bakery.plugins.builtin.imagetools.options import SociOptions
from posit_bakery.plugins.builtin.imagetools.publish import SOCI_PHASES

pytestmark = [pytest.mark.unit]


def _make_target(uid: str, image_name: str = "test-image") -> ImageTarget:
    t = MagicMock(spec=ImageTarget)
    t.uid = uid
    t.image_name = image_name
    t.temp_registry = "ghcr.io/posit-dev"
    t.push_sort_key = (uid,)
    t.__str__ = lambda self: f"ImageTarget({uid})"
    return t


def _execute_soci(plugin, tmp_path, target):
    return plugin.execute(
        base_path=tmp_path, targets=[target], source_refs={target.uid: "ref"}, phases=SOCI_PHASES, dry_run=True
    )


def test_dry_run_disabled_target_exits_zero(tmp_path):
    with patch(
        "posit_bakery.plugins.builtin.imagetools.soci.get_soci_options_for_target",
        return_value=SociOptions(enabled=False),
    ):
        results = _execute_soci(ImageToolsPlugin(), tmp_path, _make_target("a"))
    assert [r.exit_code for r in results] == [0]


def test_dry_run_enabled_target_exits_zero(tmp_path):
    with patch(
        "posit_bakery.plugins.builtin.imagetools.soci.get_soci_options_for_target",
        return_value=SociOptions(enabled=True),
    ):
        results = _execute_soci(ImageToolsPlugin(), tmp_path, _make_target("a"))
    assert [r.exit_code for r in results] == [0]


@pytest.fixture
def missing_tools(monkeypatch):
    """Simulate a host where soci/oras are not installed anywhere."""
    real_which = util.which
    monkeypatch.setattr(util, "which", lambda name: None if name in {"soci", "oras"} else real_which(name))
    for env in ("SOCI_PATH", "ORAS_PATH"):
        monkeypatch.delenv(env, raising=False)


def test_dry_run_does_not_require_tools_installed(tmp_path, missing_tools):
    """A dry run executes nothing, so it must not abort when soci/oras are absent. Regression:
    `ci publish --dry-run` raised BakeryToolNotFoundError when binaries were resolved eagerly."""
    with patch(
        "posit_bakery.plugins.builtin.imagetools.soci.get_soci_options_for_target",
        return_value=SociOptions(enabled=True),
    ):
        results = _execute_soci(ImageToolsPlugin(), tmp_path, _make_target("a"))
    assert [r.exit_code for r in results] == [0]
