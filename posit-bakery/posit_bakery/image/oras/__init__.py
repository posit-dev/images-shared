"""ORAS CLI integration for multi-platform manifest management."""

from posit_bakery.image.oras.oras import (
    find_oras_bin,
    get_repository_from_ref,
    parse_image_reference,
    OrasCommand,
    OrasCopy,
    OrasManifestDelete,
    OrasManifestIndexCreate,
    OrasMergeWorkflow,
    OrasMergeWorkflowResult,
)

__all__ = [
    "find_oras_bin",
    "get_repository_from_ref",
    "parse_image_reference",
    "OrasCommand",
    "OrasCopy",
    "OrasManifestDelete",
    "OrasManifestIndexCreate",
    "OrasMergeWorkflow",
    "OrasMergeWorkflowResult",
]
