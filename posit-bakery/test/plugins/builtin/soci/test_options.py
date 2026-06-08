"""Tests for SociOptions."""

import pytest

from posit_bakery.plugins.builtin.soci.options import SociModeEnum, SociOptions

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
    assert opts.candidate_namespaces is None


def test_overrides():
    opts = SociOptions(
        enabled=True,
        span_size=4 * 1024 * 1024,
        min_layer_size=10 * 1024 * 1024,
        prefetch_files=["/a", "/b"],
        optimizations=["xattr"],
        platforms=["linux/amd64"],
        candidate_namespaces=["moby"],
    )
    assert opts.enabled is True
    assert opts.span_size == 4 * 1024 * 1024
    assert opts.min_layer_size == 10 * 1024 * 1024
    assert opts.prefetch_files == ["/a", "/b"]
    assert opts.optimizations == ["xattr"]
    assert opts.platforms == ["linux/amd64"]
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


def test_update_other_wins_for_list_fields_when_self_unset():
    base = SociOptions()
    override = SociOptions(prefetch_files=["/a"], optimizations=["xattr"])
    merged = base.update(override)
    assert merged.prefetch_files == ["/a"]
    assert merged.optimizations == ["xattr"]


def test_update_self_wins_for_list_fields_when_explicitly_set():
    base = SociOptions(prefetch_files=["/x"], optimizations=["yyy"])
    override = SociOptions(prefetch_files=["/a"], optimizations=["xattr"])
    merged = base.update(override)
    assert merged.prefetch_files == ["/x"]
    assert merged.optimizations == ["yyy"]


def test_update_scalar_explicitly_set_to_default():
    """User explicitly sets a scalar to its default value; self should still win."""
    base = SociOptions(enabled=False)  # explicitly set to default False
    override = SociOptions(enabled=True)
    merged = base.update(override)
    # enabled is in base.model_fields_set, so base's value should win
    assert merged.enabled is False


def test_update_list_explicitly_set_to_empty():
    """User explicitly sets a list to empty (its default); self should still win."""
    base = SociOptions(prefetch_files=[])  # explicitly set to []
    override = SociOptions(prefetch_files=["/a"])
    merged = base.update(override)
    # prefetch_files is in base.model_fields_set, so base's value should win
    assert merged.prefetch_files == []


def test_soci_mode_enum_values():
    assert SociModeEnum.CONTAINERD.value == "containerd"
    assert SociModeEnum.STANDALONE.value == "standalone"
    assert SociModeEnum("standalone") is SociModeEnum.STANDALONE
