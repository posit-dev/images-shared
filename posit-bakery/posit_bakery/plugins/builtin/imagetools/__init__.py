"""imagetools plugin: merge (ORAS) and SOCI-convert multi-platform images.

This package merges the former standalone ``oras`` and ``soci`` plugins into a
single plugin, since they are almost exclusively used together in CI (see the
``bakery ci publish`` orchestration).
"""

from posit_bakery.plugins.builtin.imagetools.imagetools import (
    ImageToolsPlugin,
    get_soci_options_for_target,
)
from posit_bakery.plugins.builtin.imagetools.oras import find_oras_bin
from posit_bakery.plugins.builtin.imagetools.soci import find_soci_bin

__all__ = [
    "ImageToolsPlugin",
    "get_soci_options_for_target",
    "find_oras_bin",
    "find_soci_bin",
]
