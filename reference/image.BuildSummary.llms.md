# image.BuildSummary

# image.BuildSummary

Counts (and, once a build has produced artifacts, sizes) for a set of image targets.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/summary.py#L254-L595)

``` python
image.BuildSummary()
```

## Methods

| Name | Description |
|----|----|
| [as_dict()](#as_dict) | Flatten to a CI-friendly dict for `--summary-format json`. |
| [from_image_targets()](#from_image_targets) | Compute build and artifact counts for the given image targets. |
| [from_json_file()](#from_json_file) | Reconstructs a `BuildSummary` from a file written by `--summary-format json` |
| [measure_sizes()](#measure_sizes) | Populate registry size, local size, layer count, and cache size for each target via real I/O. |
| [merge()](#merge) | Combines multiple summaries into one, deduped by `BuildSummaryTarget.uid`. |
| [table()](#table) | Render the summary as a Rich table. |
| [to_markdown()](#to_markdown) | Renders this summary as a GitHub-Flavored Markdown report, for a GitHub job or |

### as_dict()

Flatten to a CI-friendly dict for `--summary-format json`.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/summary.py#L362-L375)

``` python
as_dict()
```

Aggregate counts are top-level keys (unchanged since Phase 1). `registry_size_bytes` and `local_size_bytes` are `null` when nothing could be measured – never `0`, which would misreport “we measured nothing” as “we measured empty”. `targets` gives the full per-target breakdown for consumers that want it.

### from_image_targets()

Compute build and artifact counts for the given image targets.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/summary.py#L260-L298)

``` python
from_image_targets(targets, *, platforms=None)
```

Performs no I/O: every count is derived from configuration already resolved onto the targets, so this is safe to call for both `--plan` and real builds.

#### Parameters

`targets``:`` ``list[ImageTarget]`  
The resolved image targets to summarize.

`platforms``:`` ``list[str] | None`` ``=`` ``None`  
The `--image-platform` CLI override, if any. A target that survives that filter keeps its full declared `image_os.platforms` list unchanged (`config/config.py:1056-1071` is an any-match gate, not a narrowing one) — the actual narrowing to fewer platforms happens later, uniformly across targets, via this same value (`image_target.py:664`: `platforms or (...)`). Passing it here keeps the count matching what will actually build.

### from_json_file()

Reconstructs a `BuildSummary` from a file written by `--summary-format json`

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/summary.py#L310-L322)

``` python
from_json_file(path)
```

(either `bakery build` or `bakery ci publish`).

Rebuilds `targets` from the dumped `targets` list and recomputes the three aggregate rows from that list, rather than trusting the file’s own top-level counts – keeps a single source of truth for how aggregates are derived, shared with `merge()` below.

### measure_sizes()

Populate registry size, local size, layer count, and cache size for each target via real I/O.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/summary.py#L377-L474)

``` python
measure_sizes(targets, *, push, load, jobs=None, succeeded_uids=None)
```

Never raises: a failed measurement leaves that target’s fields as `None` (rendered as a dash), logged at debug – a registry hiccup or a target that never built must never fail the build itself.

#### Parameters

`targets``:`` ``list[ImageTarget]`  
The same image targets `from_image_targets` was built from. Needed here (unlike the zero-I/O counts) because measurement keys off `ImageTarget.ref()`. A target under `--temp-registry` with no build metadata is skipped entirely – see `_measurable_ref()` for why measuring it would be worse than not measuring it.

`push``:`` ``bool`  
Whether this build pushed to a registry – gates the registry size lookup. Cache size is not gated on this: `cache_from` pulls whatever is at `cache_ref` regardless of `push` (only `cache_to`, the write side, requires it), so the ref is just as measurable on a pull-only build.

`load``:`` ``bool`  
Whether this build loaded to the local daemon – gates the local size lookup.

`jobs``:`` ``int | None`` ``=`` ``None`  
Maximum concurrent inspects; defaults to `SETTINGS.max_concurrency`.

`succeeded_uids``:`` ``set[str] | None`` ``=`` ``None`  
UIDs that succeeded in this build run, if known – further narrows the registry size lookup so a target that failed this run isn’t measured off whatever image happens to already be sitting at its tag from an earlier, unrelated push. `None` (the default) skips this narrowing and measures every target whenever `push` is true, matching the original behavior; `--strategy bake` has no per-target result to give, so it always passes `None`.

### merge()

Combines multiple summaries into one, deduped by `BuildSummaryTarget.uid`.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/summary.py#L324-L360)

``` python
merge(summaries)
```

`uid` has no platform component, so the same uid can appear in more than one input summary – e.g. one JSON file per platform for a multi-platform target, or a build-time file and a separate publish-time file for the same target. Slices sharing a uid are folded into a single row:

- `platforms`, `registry_size`, `local_size` are summed: each slice reports only what it measured (its own platform’s share), so summing reconstructs the true total, the same way a single combined multi-platform registry inspect already sums across manifest children internally.
- `tags`, `layers`, `cache_ref`, `cache_size` take the first non-`None` value across a uid’s slices – they describe the whole manifest, not one platform’s share, so summing them would be wrong (and, for `cache_size`, would double-count a cache tag shared by more than one platform slice).

Aggregate rows are recomputed from the merged, deduped-by-uid target list – never by summing each input’s own aggregate rows, which would double-count any uid appearing in more than one input.

### table()

Render the summary as a Rich table.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/summary.py#L476-L528)

``` python
table(*, sizes)
```

#### Parameters

`sizes``:`` ``bool`  
`False` renders the three aggregate count rows only (unchanged since Phase 1). `True` renders a per-target breakdown – one row per image target, grouped/nested by image, version, OS, and variant with repeated identity values blanked (mirroring the Goss test report’s table), plus a closing `Total` row. A target whose size wasn’t measured (build failure, or `measure_sizes()` never called) shows a dash rather than a misleading zero.

### to_markdown()

Renders this summary as a GitHub-Flavored Markdown report, for a GitHub job or

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/summary.py#L530-L595)

``` python
to_markdown(*, disclaimer=None)
```

run summary. Always renders the full per-target breakdown – a summary page reader wants the detail, not just the three aggregate counts a terminal caller sees by default without `--summary-format table`’s sizes view.

#### Parameters

`disclaimer``:`` ``str | None`` ``=`` ``None`  
If given, prepended as a warning-styled blockquote ahead of the table – e.g. “this run had failures, so these totals are incomplete.”

Back to top
