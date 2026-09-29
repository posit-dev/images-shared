"""Guard against committed rendered fixtures drifting from their templates.

Image build tests (pytest `@image_build` scenarios and the CI blackbox job) build the
committed rendered files, not freshly rendered ones. Without this check, a macro change
that isn't re-rendered into these fixtures would still pass CI.
"""

import filecmp
import shutil
from pathlib import Path

import pytest

from posit_bakery.config import BakeryConfig

pytestmark = [
    pytest.mark.unit,
]

# Test contexts whose rendered output is built and tested against real images.
RENDERED_CONTEXTS = [
    "with-macros",
    "macros-functional",
]


def _diff_trees(left: Path, right: Path) -> list[str]:
    """Return relative paths that differ, or exist on only one side, between two trees."""
    diffs = []
    cmp = filecmp.dircmp(left, right)
    for name in cmp.left_only:
        diffs.append(f"only in committed: {name}")
    for name in cmp.right_only:
        diffs.append(f"only in rendered: {name}")
    # dircmp compares shallowly by stat signature; recompare contents explicitly.
    _, mismatch, errors = filecmp.cmpfiles(left, right, cmp.common_files, shallow=False)
    diffs.extend(f"differs: {name}" for name in mismatch + errors)
    for sub in cmp.common_dirs:
        for d in _diff_trees(left / sub, right / sub):
            kind, path = d.split(": ", 1)
            diffs.append(f"{kind}: {sub}/{path}")
    return diffs


@pytest.mark.parametrize("suite_name", RENDERED_CONTEXTS)
def test_rendered_fixtures_match_templates(get_context, tmp_path, suite_name):
    """Re-render every image version and assert the output matches what is committed."""
    committed = get_context(suite_name)
    rendered = tmp_path / suite_name
    shutil.copytree(committed, rendered)

    config = BakeryConfig.from_context(rendered)
    config.rerender_files()

    diffs = _diff_trees(committed, rendered)
    assert not diffs, (
        f"Rendered files in '{suite_name}' are out of date with their templates. Re-render with "
        f"`bakery update files --all --context test/resources/{suite_name}`:\n  " + "\n  ".join(diffs)
    )
