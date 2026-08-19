import json
import logging
from pathlib import Path
from typing import Any, Self

import python_on_whales
from pydantic import BaseModel, Field, ValidationError
from python_on_whales.components.buildx.imagetools.models import Manifest
from python_on_whales.components.image.models import ImageInspectResult
from rich.filesize import decimal as format_size
from rich.table import Table
from rich.text import Text

from posit_bakery.config.image.build_os import DEFAULT_PLATFORMS
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.parallel import CommandRunner, JobResult, ParallelShellExecutor, ShellJob, resolve_max_workers
from posit_bakery.reporting import GroupColumn, ValueColumn, grouped_table

log = logging.getLogger(__name__)

TAG_ALIAS_NOTE = (
    "Registry Tags counts tag aliases (version, os, latest, etc.) across registries, not distinct stored images."
)

LAYER_COUNT_NOTE = (
    "Layers is one platform's manifest layer count; Registry Size sums every platform in a multi-platform index."
)

SIZES_CAPTION = f"{TAG_ALIAS_NOTE}\n{LAYER_COUNT_NOTE}"

DASH = "—"


def _dash() -> Text:
    return Text(DASH, style="bright_black italic")


def _docker_cmd() -> list[str]:
    return [str(part) for part in python_on_whales.docker.docker_cmd]


def _inspect_local(ref: str) -> python_on_whales.Image | None:
    """Inspects `ref` against the local daemon via python-on-whales; `None` on any failure
    (image absent, daemon unreachable, malformed output, etc.).

    Goes through `python_on_whales.docker.image.inspect()` rather than `CommandRunner`: a
    local daemon read is a single quick metadata call with no meaningful duration to bound,
    so `CommandRunner`'s tracked-spawn machinery (timeout enforcement, Ctrl-C process-group
    teardown) buys nothing here, and python-on-whales already does the same JSON
    parse/validate this function used to do by hand.

    `_inspect_manifest`/`_inspect_registry` still shell out through `CommandRunner` despite
    `python_on_whales.docker.buildx.imagetools.inspect()` wrapping the identical command --
    their call is a registry round trip, not a local read, and can hang (a stalled
    connection, a slow registry); `CommandRunner`'s timeout enforcement and Ctrl-C
    process-group teardown are what actually bound that, and python-on-whales's own `run()`
    has neither.
    """
    try:
        return python_on_whales.docker.image.inspect(ref)
    except python_on_whales.exceptions.DockerException as e:
        log.debug(f"Could not inspect local image '{ref}': {e}")
        return None


def _repository_of(ref: str) -> str:
    """Strips a trailing `:tag`, `@digest`, or `:tag@digest` from `ref`, without misparsing
    a `host:port` registry. `ImageTarget.ref()` returns a `repo:tag@digest` reference
    whenever build metadata is available, so the digest suffix has to go first -- otherwise
    the split on the last `:` lands inside the digest's own hex, not at the tag separator.
    """
    ref = ref.split("@", 1)[0]
    name = ref.rsplit("/", 1)[-1]
    return ref.rsplit(":", 1)[0] if ":" in name else ref


def _inspect_manifest(runner: CommandRunner, ref: str) -> Manifest | None:
    """Runs `docker buildx imagetools inspect --raw <ref>`; `None` on any failure.

    Deliberately via `CommandRunner`, not `python_on_whales.docker.buildx.imagetools.inspect()`
    -- see `_inspect_local`'s docstring for why a registry round trip keeps `CommandRunner`'s
    timeout/interrupt handling while a local daemon read doesn't need it.
    """
    result = runner.run([*_docker_cmd(), "buildx", "imagetools", "inspect", "--raw", ref])
    if result.returncode != 0:
        log.debug(f"Could not inspect registry manifest '{ref}': {result.stderr.decode(errors='replace').strip()}")
        return None
    try:
        return Manifest(**json.loads(result.stdout))
    except (json.JSONDecodeError, ValidationError) as e:
        log.debug(f"Could not parse registry manifest for '{ref}': {e}")
        return None


def _inspect_registry(runner: CommandRunner, ref: str) -> tuple[int, int] | None:
    """Returns `(total layer bytes, layer count)` for `ref` in its registry, or `None`.

    A multi-platform index costs 1+N round trips: `imagetools inspect` on an index returns
    child descriptors (`Manifest.manifests[]`), not layers, so each child digest needs its own
    inspect to reach real layer sizes. Byte totals sum across every image child -- that is the
    real transfer/storage cost -- while buildx's attestation manifests, which ride along in the
    same index but aren't part of the image, are skipped. Layer *count* uses only the first
    image child inspected, since summing
    layer counts across platforms doesn't make "how many layers" more meaningful the way
    summing bytes makes "how much storage" more meaningful.
    """
    manifest = _inspect_manifest(runner, ref)
    if manifest is None:
        return None

    if manifest.layers is not None:
        sizes = [layer.size for layer in manifest.layers if layer.size is not None]
        return sum(sizes), len(manifest.layers)

    if not manifest.manifests:
        return None

    repository = _repository_of(ref)
    total_size = 0
    layer_count: int | None = None
    for child in manifest.manifests:
        if child.digest is None:
            continue
        if child.platform is not None and child.platform.architecture == "unknown":
            # buildx attaches provenance/SBOM attestations to the index as extra manifests
            # under an unknown/unknown platform. Their blobs aren't part of the image, so
            # they inflate the byte total -- and, if one is inspected first, hand back the
            # attestation's layer count as the image's.
            continue
        child_manifest = _inspect_manifest(runner, f"{repository}@{child.digest}")
        if child_manifest is None or child_manifest.layers is None:
            continue
        total_size += sum(layer.size for layer in child_manifest.layers if layer.size is not None)
        if layer_count is None:
            layer_count = len(child_manifest.layers)

    if layer_count is None:
        return None
    return total_size, layer_count


def _measurable_ref(target: ImageTarget) -> str | None:
    """The reference to measure `target` against, or `None` when there isn't a trustworthy one.

    `ImageTarget.ref()` falls back to `tags[0]` -- the final, public tag -- whenever no build
    metadata is available. That fallback is wrong under `--temp-registry`: `ImageTarget.build()`
    replaces the tag list with `temp_name` and pushes by digest, so this build never writes
    those public tags. Measuring them anyway reports whatever the *previous* release left
    sitting there as if it were this build's output -- a plausible-looking number measured off
    an unrelated image, which is worse than no number at all. `--metadata-file` populates
    `build_metadata` and makes `ref()` resolve to the digest actually pushed; without it,
    under a temp registry, measure nothing.
    """
    if target.temp_name is not None and not target.build_metadata:
        return None
    return target.ref()


def _cache_size(runner: CommandRunner, ref: str) -> int | None:
    """Sums layer sizes from the manifest at a build cache ref; `None` when the manifest
    can't be fetched (no registry credentials, or a target whose build never pushed cache).

    Uses the same `imagetools inspect` path as `_inspect_registry` rather than a registry
    HTTP client, so this works for any cache registry (`--cache-registry` is not required to
    be GHCR) and reuses whatever credentials the builder already has. Unlike an image, a
    cache tag is never a multi-platform index (verified live: BuildKit's registry cache
    exporter writes one image manifest whose config is `vnd.buildkit.cacheconfig.v0`), so
    there is no child fan-out to do here.
    """
    manifest = _inspect_manifest(runner, ref)
    if manifest is None or manifest.layers is None:
        return None
    return sum(layer.size for layer in manifest.layers if layer.size is not None)


def _sum_or_none(values: list[int | None]) -> int | None:
    """Sums whichever of `values` are known; `None` (not `0`) when none are, since "0" would
    misreport "we measured nothing" as "we measured empty"."""
    known = [v for v in values if v is not None]
    return sum(known) if known else None


def _combine_optional(a: int | None, b: int | None) -> int | None:
    """Sums two optional platform-scoped values: `None` only when both are `None` --
    matches `_sum_or_none`'s "unmeasured, not zero" rule for a two-value merge."""
    if a is None and b is None:
        return None
    return (a or 0) + (b or 0)


def _first_non_none(a: Any, b: Any) -> Any:
    """The first non-`None` of two identity-field values -- used for fields that must
    never be summed across platform slices of the same target (tags, layers, cache_ref,
    cache_size), since they describe the whole manifest, not one platform's share of it."""
    return a if a is not None else b


def _total_bytes(values: list[int | None]) -> str:
    total = _sum_or_none(values)
    return format_size(total) if total is not None else DASH


class BuildSummaryRow(BaseModel):
    """A single labeled metric in a build summary report."""

    key: str
    label: str
    value: int


class BuildSummaryTarget(BaseModel):
    """Per-target row for the sizes view of a build summary."""

    uid: str
    image_name: str
    version: str
    os: str
    variant: str
    platforms: int
    tags: int
    layers: int | None = None
    registry_size: int | None = None
    local_size: int | None = None
    cache_ref: str | None = None
    cache_size: int | None = None


def _deduped_cache_sizes(targets: list[BuildSummaryTarget]) -> list[int | None]:
    """One `cache_size` per distinct `cache_ref` among `targets`.

    A true multi-platform target's cache tag has no arch suffix (`ImageTarget.cache_name()`),
    so more than one row can carry the same ref -- summing every row directly would double
    (or N-times) count that shared cache. Rows without a `cache_ref` (no `--cache-registry`
    configured) contribute nothing, same as an unmeasured size.
    """
    seen: dict[str, int | None] = {}
    for target in targets:
        if target.cache_ref is not None and target.cache_ref not in seen:
            seen[target.cache_ref] = target.cache_size
    return list(seen.values())


class BuildSummary(BaseModel):
    """Counts (and, once a build has produced artifacts, sizes) for a set of image targets."""

    rows: list[BuildSummaryRow]
    targets: list[BuildSummaryTarget] = Field(default_factory=list)

    @classmethod
    def from_image_targets(cls, targets: list[ImageTarget], *, platforms: list[str] | None = None) -> Self:
        """Compute build and artifact counts for the given image targets.

        Performs no I/O: every count is derived from configuration already resolved onto
        the targets, so this is safe to call for both `--plan` and real builds.

        :param targets: The resolved image targets to summarize.
        :param platforms: The `--image-platform` CLI override, if any. A target that
            survives that filter keeps its full declared `image_os.platforms` list
            unchanged (`config/config.py:1056-1071` is an any-match gate, not a narrowing
            one) — the actual narrowing to fewer platforms happens later, uniformly across
            targets, via this same value (`image_target.py:664`: `platforms or (...)`).
            Passing it here keeps the count matching what will actually build.
        """
        build_platforms = [
            platforms or (target.image_os.platforms if target.image_os else DEFAULT_PLATFORMS) for target in targets
        ]
        platform_counts = [len(bp) for bp in build_platforms]
        registry_tags = sum(len(target.tags) for target in targets)

        target_rows = [
            BuildSummaryTarget(
                uid=target.uid,
                image_name=target.image_name,
                version=target.image_version.name,
                os=target.image_os.name if target.image_os else "",
                variant=target.image_variant.name if target.image_variant else "",
                platforms=platform_count,
                tags=len(target.tags),
                cache_ref=target.cache_name(platform=bp[0] if len(bp) == 1 else None),
            )
            for target, platform_count, bp in zip(targets, platform_counts, build_platforms)
        ]

        return cls(
            rows=cls._aggregate_rows(target_rows),
            targets=target_rows,
        )

    @staticmethod
    def _aggregate_rows(targets: list[BuildSummaryTarget]) -> list[BuildSummaryRow]:
        """The three aggregate rows, derived from a target list -- the single source of
        truth `from_image_targets`, `from_json_file`, and `merge` all share."""
        return [
            BuildSummaryRow(key="build_targets", label="Build Targets", value=len(targets)),
            BuildSummaryRow(key="platform_builds", label="Platform Builds", value=sum(t.platforms for t in targets)),
            BuildSummaryRow(key="registry_tags", label="Registry Tags", value=sum(t.tags for t in targets)),
        ]

    @classmethod
    def from_json_file(cls, path: Path) -> Self:
        """Reconstructs a `BuildSummary` from a file written by `--summary-format json`
        (either `bakery build` or `bakery ci publish`).

        Rebuilds `targets` from the dumped `targets` list and recomputes the three
        aggregate rows from that list, rather than trusting the file's own top-level
        counts -- keeps a single source of truth for how aggregates are derived, shared
        with `merge()` below.
        """
        data = json.loads(path.read_text())
        targets = [BuildSummaryTarget(**t) for t in data.get("targets", [])]
        return cls(rows=cls._aggregate_rows(targets), targets=targets)

    @classmethod
    def merge(cls, summaries: list[Self]) -> Self:
        """Combines multiple summaries into one, deduped by `BuildSummaryTarget.uid`.

        `uid` has no platform component, so the same uid can appear in more than one
        input summary -- e.g. one JSON file per platform for a multi-platform target, or
        a build-time file and a separate publish-time file for the same target. Slices
        sharing a uid are folded into a single row:

        - `platforms`, `registry_size`, `local_size` are summed: each slice reports only
          what it measured (its own platform's share), so summing reconstructs the true
          total, the same way a single combined multi-platform registry inspect already
          sums across manifest children internally.
        - `tags`, `layers`, `cache_ref`, `cache_size` take the first non-`None` value
          across a uid's slices -- they describe the whole manifest, not one platform's
          share, so summing them would be wrong (and, for `cache_size`, would double-count
          a cache tag shared by more than one platform slice).

        Aggregate rows are recomputed from the merged, deduped-by-uid target list --
        never by summing each input's own aggregate rows, which would double-count any
        uid appearing in more than one input.
        """
        merged: dict[str, BuildSummaryTarget] = {}
        for summary in summaries:
            for target in summary.targets:
                if target.uid not in merged:
                    merged[target.uid] = target.model_copy(deep=True)
                    continue
                base = merged[target.uid]
                base.platforms += target.platforms
                base.registry_size = _combine_optional(base.registry_size, target.registry_size)
                base.local_size = _combine_optional(base.local_size, target.local_size)
                base.layers = _first_non_none(base.layers, target.layers)
                base.cache_ref = _first_non_none(base.cache_ref, target.cache_ref)
                base.cache_size = _first_non_none(base.cache_size, target.cache_size)
        merged_targets = list(merged.values())
        return cls(rows=cls._aggregate_rows(merged_targets), targets=merged_targets)

    def as_dict(self) -> dict[str, Any]:
        """Flatten to a CI-friendly dict for `--summary-format json`.

        Aggregate counts are top-level keys (unchanged since Phase 1). `registry_size_bytes`
        and `local_size_bytes` are `null` when nothing could be measured -- never `0`, which
        would misreport "we measured nothing" as "we measured empty". `targets` gives the
        full per-target breakdown for consumers that want it.
        """
        result: dict[str, Any] = {row.key: row.value for row in self.rows}
        result["registry_size_bytes"] = _sum_or_none([target.registry_size for target in self.targets])
        result["local_size_bytes"] = _sum_or_none([target.local_size for target in self.targets])
        result["cache_size_bytes"] = _sum_or_none(_deduped_cache_sizes(self.targets))
        result["targets"] = [target.model_dump() for target in self.targets]
        return result

    def measure_sizes(
        self,
        targets: list[ImageTarget],
        *,
        push: bool,
        load: bool,
        jobs: int | None = None,
        succeeded_uids: set[str] | None = None,
    ) -> None:
        """Populate registry size, local size, layer count, and cache size for each target via real I/O.

        Never raises: a failed measurement leaves that target's fields as `None` (rendered as
        a dash), logged at debug -- a registry hiccup or a target that never built must never
        fail the build itself.

        :param targets: The same image targets `from_image_targets` was built from. Needed
            here (unlike the zero-I/O counts) because measurement keys off `ImageTarget.ref()`.
            A target under `--temp-registry` with no build metadata is skipped entirely -- see
            `_measurable_ref()` for why measuring it would be worse than not measuring it.
        :param push: Whether this build pushed to a registry -- gates the registry size lookup.
            Cache size is not gated on this: `cache_from` pulls whatever is at `cache_ref`
            regardless of `push` (only `cache_to`, the write side, requires it), so the ref is
            just as measurable on a pull-only build.
        :param load: Whether this build loaded to the local daemon -- gates the local size lookup.
        :param jobs: Maximum concurrent inspects; defaults to `SETTINGS.max_concurrency`.
        :param succeeded_uids: UIDs that succeeded in this build run, if known -- further
            narrows the registry size lookup so a target that failed this run isn't measured
            off whatever image happens to already be sitting at its tag from an earlier,
            unrelated push. `None` (the default) skips this narrowing and measures every
            target whenever `push` is true, matching the original behavior; `--strategy bake`
            has no per-target result to give, so it always passes `None`.
        """
        has_cache_ref = any(row.cache_ref is not None for row in self.targets)
        if not push and not load and not has_cache_ref:
            return

        rows_by_uid = {row.uid: row for row in self.targets}
        # Read on the main thread and bound into each job below, so a worker never reaches
        # into a row -- not even to read one. Rows are `_apply`'s alone.
        cache_refs = {row.uid: row.cache_ref for row in self.targets}

        def _measure(
            runner: CommandRunner, target: ImageTarget, cache_ref: str | None
        ) -> tuple[int | None, int | None, int | None, int | None]:
            """Runs on a worker thread. Returns (local_size, registry_size, layers, cache_size)
            instead of writing to `row` directly -- mutation happens in `_apply`, on the main
            thread, via `on_result`, matching ParallelShellExecutor's own documented safe
            pattern. `cache_ref` is passed in for the same reason, rather than looked up from
            `rows_by_uid` here."""
            local_size = registry_size = layers = cache_size = None
            local_layers = registry_layers = None
            try:
                # `None` when this build's own artifact isn't addressable (see
                # `_measurable_ref`); the cache ref below is independent of it.
                ref = _measurable_ref(target)
                if ref is not None and load:
                    local_result = _inspect_local(ref)
                    if local_result is not None:
                        local_size = local_result.size
                        if local_result.root_fs is not None and local_result.root_fs.layers is not None:
                            local_layers = len(local_result.root_fs.layers)
                if ref is not None and push and (succeeded_uids is None or target.uid in succeeded_uids):
                    registry_result = _inspect_registry(runner, ref)
                    if registry_result is not None:
                        registry_size, registry_layers = registry_result
                # The manifest's blob count wins over the local rootfs diff-ID count: the two
                # measure different things (a metadata-only layer has a blob but no diff ID),
                # and the manifest describes what actually ships. Fixing the precedence keeps
                # the column's meaning from flipping with `--load`/`--push`; the local count is
                # only a fallback for builds that never touch a registry.
                layers = registry_layers if registry_layers is not None else local_layers
                if cache_ref is not None:
                    cache_size = _cache_size(runner, cache_ref)
            except Exception as e:
                log.debug(f"Could not measure size for '{target}': {e}")
            return local_size, registry_size, layers, cache_size

        def _apply(job_result: JobResult) -> None:
            """Runs on the main thread: the only place that writes to a row."""
            if job_result.value is None:
                return
            row = rows_by_uid.get(job_result.job.key)
            if row is None:
                return
            row.local_size, row.registry_size, row.layers, row.cache_size = job_result.value

        executor = ParallelShellExecutor(max_workers=resolve_max_workers(jobs, len(targets)))
        executor.run_jobs(
            [
                ShellJob(
                    key=target.uid,
                    label=str(target),
                    run=lambda runner, t=target, c=cache_refs.get(target.uid): _measure(runner, t, c),
                )
                for target in targets
            ],
            on_result=_apply,
        )

    def table(self, *, sizes: bool) -> Table:
        """Render the summary as a Rich table.

        :param sizes: `False` renders the three aggregate count rows only (unchanged since
            Phase 1). `True` renders a per-target breakdown -- one row per image target,
            grouped/nested by image, version, OS, and variant with repeated identity values
            blanked (mirroring the Goss test report's table), plus a closing `Total` row.
            A target whose size wasn't measured (build failure, or `measure_sizes()` never
            called) shows a dash rather than a misleading zero.
        """
        if not sizes:
            table = Table(title="Build Summary", caption=TAG_ALIAS_NOTE)
            table.add_column("Metric", justify="left")
            table.add_column("Count", justify="right")
            for row in self.rows:
                table.add_row(row.label, str(row.value))
            return table

        sorted_targets = sorted(self.targets, key=lambda t: (t.image_name, t.version, t.os, t.variant))

        return grouped_table(
            sorted_targets,
            title=f"Build Summary ({len(sorted_targets)} targets)",
            caption=SIZES_CAPTION,
            group_columns=[
                GroupColumn("Image", lambda t: t.image_name),
                GroupColumn("Version", lambda t: t.version),
                GroupColumn("OS", lambda t: t.os),
                GroupColumn("Variant", lambda t: t.variant),
            ],
            value_columns=[
                ValueColumn(
                    "Platforms", lambda t: str(t.platforms), total=lambda ts: str(sum(t.platforms for t in ts))
                ),
                ValueColumn("Tags", lambda t: str(t.tags), total=lambda ts: str(sum(t.tags for t in ts))),
                ValueColumn("Layers", lambda t: str(t.layers) if t.layers is not None else _dash()),
                ValueColumn(
                    "Registry Size",
                    lambda t: format_size(t.registry_size) if t.registry_size is not None else _dash(),
                    total=lambda ts: _total_bytes([t.registry_size for t in ts]),
                ),
                ValueColumn(
                    "Local Size",
                    lambda t: format_size(t.local_size) if t.local_size is not None else _dash(),
                    total=lambda ts: _total_bytes([t.local_size for t in ts]),
                ),
                ValueColumn(
                    "Cache Size",
                    lambda t: format_size(t.cache_size) if t.cache_size is not None else _dash(),
                    total=lambda ts: _total_bytes(_deduped_cache_sizes(ts)),
                ),
            ],
        )
