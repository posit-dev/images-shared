"""Tests for SociOptions."""

import pytest

from posit_bakery.plugins.builtin.soci.options import SociOptions

pytestmark = [pytest.mark.unit]


def test_defaults():
    opts = SociOptions()
    assert opts.tool == "soci"
    assert opts.enabled is False
    assert opts.span_size is None
    assert opts.min_layer_size is None
    assert opts.prefetch_files == []
    assert opts.optimizations == []
    assert opts.platforms is None
    assert opts.standalone is None
    assert opts.candidate_namespaces is None


def test_overrides():
    opts = SociOptions(
        enabled=True,
        span_size=4 * 1024 * 1024,
        min_layer_size=10 * 1024 * 1024,
        prefetch_files=["/a", "/b"],
        optimizations=["xattr"],
        platforms=["linux/amd64"],
        standalone=False,
        candidate_namespaces=["moby"],
    )
    assert opts.enabled is True
    assert opts.span_size == 4 * 1024 * 1024
    assert opts.min_layer_size == 10 * 1024 * 1024
    assert opts.prefetch_files == ["/a", "/b"]
    assert opts.optimizations == ["xattr"]
    assert opts.platforms == ["linux/amd64"]
    assert opts.standalone is False
    assert opts.candidate_namespaces == ["moby"]


def test_update_other_wins_when_self_unset():
    base = SociOptions()
    override = SociOptions(enabled=True, span_size=8 * 1024 * 1024)
    merged = base.update(override)
    assert merged.enabled is True
    assert merged.span_size == 8 * 1024 * 1024


def test_update_self_wins_when_explicitly_set():
    base = SociOptions(enabled=True, span_size=16 * 1024 * 1024)
    override = SociOptions(enabled=False, span_size=8 * 1024 * 1024)
    merged = base.update(override)
    assert merged.enabled is True
    assert merged.span_size == 16 * 1024 * 1024
