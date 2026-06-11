"""Per-target publish pipeline: oras index-create -> soci convert -> oras index-copy ->
oras verify, executed through a CommandRunner so each registry command is tracked and
retried-with-backoff. One PublishWorkflow runs per target; the plugin fans targets out across
the parallel executor.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

# Referenced via their module objects (not direct names) so that monkeypatching the workflow
# classes and option lookup on these modules is honoured at call time.
from posit_bakery.plugins.builtin.imagetools import oras as oras_mod
from posit_bakery.plugins.builtin.imagetools import soci as soci_mod

if TYPE_CHECKING:
    from posit_bakery.image.image_target import ImageTarget
    from posit_bakery.parallel import CommandRunner

log = logging.getLogger(__name__)


class PublishPhase(str, Enum):
    """A stage of the publish pipeline. Phase subsets back the standalone entrypoints."""

    CREATE = "create"
    SOCI = "soci"
    COPY = "copy"
    VERIFY = "verify"


ALL_PHASES = frozenset(PublishPhase)
MERGE_PHASES = frozenset({PublishPhase.CREATE, PublishPhase.COPY})  # bakery oras merge
SOCI_PHASES = frozenset({PublishPhase.SOCI})  # bakery soci convert


@dataclass
class PublishResult:
    """Outcome of running the pipeline for one target."""

    target: "ImageTarget"
    success: bool = True
    skipped: bool = False
    skip_reason: str | None = None
    temp_ref: str | None = None
    destinations: list[str] = field(default_factory=list)
    verified: list[str] = field(default_factory=list)
    soci_destination_ref: str | None = None
    soci_skipped: bool = False
    error: str | None = None
    failed_phase: str | None = None


class PublishWorkflow:
    """Run the (subset of the) publish pipeline for a single image target through a runner.

    ``source_ref`` seeds the pipeline when CREATE is not part of ``phases`` (the soci-only
    standalone path, where the ref comes from build metadata rather than an index-create).
    """

    def __init__(
        self,
        *,
        image_target: "ImageTarget",
        oras_bin: str,
        soci_bin: str,
        source_ref: str | None = None,
    ) -> None:
        self.image_target = image_target
        self.oras_bin = oras_bin
        self.soci_bin = soci_bin
        self.source_ref = source_ref

    def run(
        self,
        runner: "CommandRunner",
        *,
        phases: frozenset[PublishPhase] = ALL_PHASES,
        dry_run: bool = False,
    ) -> PublishResult:
        target = self.image_target
        result = PublishResult(target=target)
        temp_ref = self.source_ref

        if PublishPhase.CREATE in phases:
            if not target.get_merge_sources():
                result.skipped = True
                result.skip_reason = "no merge sources"
                return result
            if not target.settings.temp_registry:
                result.success = False
                result.failed_phase = "create"
                result.error = f"temp_registry not configured for '{target}'"
                return result
            create = oras_mod.OrasIndexCreateWorkflow(
                oras_bin=self.oras_bin,
                image_target=target,
                annotations=target.labels,
            ).run(dry_run=dry_run, runner=runner)
            if not create.success:
                result.success = False
                result.failed_phase = "create"
                result.error = create.error
                return result
            temp_ref = create.temp_ref
        result.temp_ref = temp_ref

        if PublishPhase.SOCI in phases:
            options = soci_mod.get_soci_options_for_target(target)
            if options.enabled and temp_ref:
                soci = soci_mod.SociConvertWorkflow(
                    soci_bin=self.soci_bin,
                    oras_bin=self.oras_bin,
                    image_target=target,
                    options=options,
                    source_ref=temp_ref,
                ).run(dry_run=dry_run, runner=runner)
                if not soci.success:
                    result.success = False
                    result.failed_phase = "soci"
                    result.error = soci.error
                    return result
                temp_ref = soci.destination_ref
                result.soci_destination_ref = temp_ref
                result.temp_ref = temp_ref
            else:
                result.soci_skipped = True

        if PublishPhase.COPY in phases:
            if not temp_ref:
                result.skipped = True
                result.skip_reason = "no source ref to copy"
                return result
            copy = oras_mod.OrasIndexCopyWorkflow(
                oras_bin=self.oras_bin,
                image_target=target,
            ).run(source=temp_ref, dry_run=dry_run, runner=runner)
            result.destinations = copy.destinations
            if not copy.success:
                result.success = False
                result.failed_phase = "copy"
                result.error = copy.error
                return result

        if PublishPhase.VERIFY in phases and not dry_run:
            verify = oras_mod.OrasIndexVerifyWorkflow(
                oras_bin=self.oras_bin,
                image_target=target,
            ).run(dry_run=dry_run, runner=runner)
            result.verified = verify.verified
            if not verify.success:
                result.success = False
                result.failed_phase = "verify"
                result.error = verify.error
                return result

        return result
