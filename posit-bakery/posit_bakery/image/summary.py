import json
import logging
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
from posit_bakery.registry_management.ghcr.manifest import GHCRManifestClient
from posit_bakery.reporting import GroupColumn, ValueColumn, grouped_table

log = logging.getLogger(__name__)

TAG_ALIAS_NOTE = (
    "Registry Tags counts tag aliases (version, os, latest, etc.) across registries, not distinct stored images."
)

DASH = "—"


def _dash() -> Text:
    return Text(DASH, style="bright_black italic")


def _docker_cmd() -> list[str]:
    return [str(part) for part in python_on_whales.docker.docker_cmd]


def _inspect_local(runner: CommandRunner, ref: str) -> ImageInspectResult | None:
    """Runs `docker image inspect <ref>` against the local daemon; `None` on any failure."""
    result = runner.run([*_docker_cmd(), "image", "inspect", ref])
    if result.returncode != 0:
        log.debug(f"Could not inspect local image '{ref}': {result.stderr.decode(errors='replace').strip()}")
        return None
    try:
        return ImageInspectResult(**json.loads(result.stdout)[0])
    except (json.JSONDecodeError, IndexError, ValidationError) as e:
        log.debug(f"Could not parse local image inspect for '{ref}': {e}")
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
    """Runs `docker buildx imagetools inspect --raw <ref>`; `None` on any failure."""
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
    inspect to reach real layer sizes. Byte totals sum across every child -- that is the real
    transfer/storage cost. Layer *count* uses only the first child inspected, since summing
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
        child_manifest = _inspect_manifest(runner, f"{repository}@{child.digest}")
        if child_manifest is None or child_manifest.layers is None:
            continue
        total_size += sum(layer.size for layer in child_manifest.layers if layer.size is not None)
        if layer_count is None:
            layer_count = len(child_manifest.layers)

    if layer_count is None:
        return None
    return total_size, layer_count


def _cache_size(client: GHCRManifestClient, ref: str) -> int | None:
    """Sums layer sizes from the GHCR v2 manifest for a build cache ref; `None` when the
    manifest can't be fetched (private repo without access, or a target whose build never
    pushed cache) -- unlike `_inspect_registry`, a cache tag is never a multi-platform index
    (verified live: cache tags are always per-platform single manifests), so there is no
    child fan-out to do here.
    """
    manifest = client.get_manifest(ref)
    if manifest is None or manifest.layers is None:
        return None
    return sum(layer.size for layer in manifest.layers if layer.size is not None)


def _sum_or_none(values: list[int | None]) -> int | None:
    """Sums whichever of `values` are known; `None` (not `0`) when none are, since "0" would
    misreport "we measured nothing" as "we measured empty"."""
    known = [v for v in values if v is not None]
    return sum(known) if known else None


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
            rows=[
                BuildSummaryRow(key="build_targets", label="Build Targets", value=len(targets)),
                BuildSummaryRow(key="platform_builds", label="Platform Builds", value=sum(platform_counts)),
                BuildSummaryRow(key="registry_tags", label="Registry Tags", value=registry_tags),
            ],
            targets=target_rows,
        )

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

    def measure_sizes(self, targets: list[ImageTarget], *, push: bool, load: bool, jobs: int | None = None) -> None:
        """Populate registry size, local size, layer count, and cache size for each target via real I/O.

        Never raises: a failed measurement leaves that target's fields as `None` (rendered as
        a dash), logged at debug -- a registry hiccup or a target that never built must never
        fail the build itself.

        :param targets: The same image targets `from_image_targets` was built from. Needed
            here (unlike the zero-I/O counts) because measurement keys off `ImageTarget.ref()`.
        :param push: Whether this build pushed to a registry -- gates the registry size lookup.
            Cache size is not gated on this: `cache_from` pulls whatever is at `cache_ref`
            regardless of `push` (only `cache_to`, the write side, requires it), so the ref is
            just as measurable on a pull-only build.
        :param load: Whether this build loaded to the local daemon -- gates the local size lookup.
        :param jobs: Maximum concurrent inspects; defaults to `SETTINGS.max_concurrency`.
        """
        has_cache_ref = any(row.cache_ref is not None for row in self.targets)
        if not push and not load and not has_cache_ref:
            return

        rows_by_uid = {row.uid: row for row in self.targets}

        manifest_client: GHCRManifestClient | None = None
        if has_cache_ref:
            try:
                manifest_client = GHCRManifestClient()
            except ValueError as e:
                log.debug(f"Cache size measurement disabled: {e}")

        def _measure(
            runner: CommandRunner, target: ImageTarget
        ) -> tuple[int | None, int | None, int | None, int | None]:
            """Runs on a worker thread. Returns (local_size, registry_size, layers, cache_size)
            instead of writing to `row` directly -- mutation happens in `_apply`, on the main
            thread, via `on_result`, matching ParallelShellExecutor's own documented safe
            pattern."""
            ref = target.ref()
            row = rows_by_uid.get(target.uid)
            local_size = registry_size = layers = cache_size = None
            try:
                if load:
                    local_result = _inspect_local(runner, ref)
                    if local_result is not None:
                        local_size = local_result.size
                        if local_result.root_fs is not None and local_result.root_fs.layers is not None:
                            layers = len(local_result.root_fs.layers)
                if push:
                    registry_result = _inspect_registry(runner, ref)
                    if registry_result is not None:
                        registry_size, registry_layers = registry_result
                        if layers is None:
                            layers = registry_layers
                if manifest_client is not None and row is not None and row.cache_ref is not None:
                    cache_size = _cache_size(manifest_client, row.cache_ref)
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
                ShellJob(key=target.uid, label=str(target), run=lambda runner, t=target: _measure(runner, t))
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
            caption=TAG_ALIAS_NOTE,
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
