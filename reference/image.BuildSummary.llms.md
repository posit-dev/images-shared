# image.BuildSummary

# image.BuildSummary

Counts (and, once a build has produced artifacts, sizes) for a set of image targets.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/summary.py#L193-L387)

``` python
image.BuildSummary()
```

## Methods

| Name | Description |
|----|----|
| [as_dict()](#as_dict) | Flatten to a CI-friendly dict for `--summary-format json`. |
| [from_image_targets()](#from_image_targets) | Compute build and artifact counts for the given image targets. |
| [measure_sizes()](#measure_sizes) | Populate registry size, local size, and layer count for each target via real I/O. |
| [table()](#table) | Render the summary as a Rich table. |

### as_dict()

Flatten to a CI-friendly dict for `--summary-format json`.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/summary.py#L244-L256)

``` python
as_dict()
```

Aggregate counts are top-level keys (unchanged since Phase 1). `registry_size_bytes` and `local_size_bytes` are `null` when nothing could be measured – never `0`, which would misreport “we measured nothing” as “we measured empty”. `targets` gives the full per-target breakdown for consumers that want it.

### from_image_targets()

Compute build and artifact counts for the given image targets.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/summary.py#L199-L242)

``` python
from_image_targets(targets, *, platforms=None)
```

Performs no I/O: every count is derived from configuration already resolved onto the targets, so this is safe to call for both `--plan` and real builds.

#### Parameters

`targets``:`` ``list[ImageTarget]`  
The resolved image targets to summarize.

`platforms``:`` ``list[str] | None`` ``=`` ``None`  
The `--image-platform` CLI override, if any. A target that survives that filter keeps its full declared `image_os.platforms` list unchanged (`config/config.py:1056-1071` is an any-match gate, not a narrowing one) — the actual narrowing to fewer platforms happens later, uniformly across targets, via this same value (`image_target.py:664`: `platforms or (...)`). Passing it here keeps the count matching what will actually build.

### measure_sizes()

Populate registry size, local size, and layer count for each target via real I/O.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/summary.py#L258-L338)

``` python
measure_sizes(targets, *, push, load, jobs=None, succeeded_uids=None)
```

Never raises: a failed measurement leaves that target’s fields as `None` (rendered as a dash), logged at debug – a registry hiccup or a target that never built must never fail the build itself.

#### Parameters

`targets``:`` ``list[ImageTarget]`  
The same image targets `from_image_targets` was built from. Needed here (unlike the zero-I/O counts) because measurement keys off `ImageTarget.ref()`. A target under `--temp-registry` with no build metadata is skipped entirely – see `_measurable_ref()` for why measuring it would be worse than not measuring it.

`push``:`` ``bool`  
Whether this build pushed to a registry – gates the registry size lookup.

`load``:`` ``bool`  
Whether this build loaded to the local daemon – gates the local size lookup.

`jobs``:`` ``int | None`` ``=`` ``None`  
Maximum concurrent inspects; defaults to `SETTINGS.max_concurrency`.

`succeeded_uids``:`` ``set[str] | None`` ``=`` ``None`  
UIDs that succeeded in this build run, if known – further narrows the registry size lookup so a target that failed this run isn’t measured off whatever image happens to already be sitting at its tag from an earlier, unrelated push. `None` (the default) skips this narrowing and measures every target whenever `push` is true, matching the original behavior; `--strategy bake` has no per-target result to give, so it always passes `None`.

### table()

Render the summary as a Rich table.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/summary.py#L340-L387)

``` python
table(*, sizes)
```

#### Parameters

`sizes``:`` ``bool`  
`False` renders the three aggregate count rows only (unchanged since Phase 1). `True` renders a per-target breakdown – one row per image target, grouped/nested by image, version, OS, and variant with repeated identity values blanked (mirroring the Goss test report’s table), plus a closing `Total` row. A target whose size wasn’t measured (build failure, or `measure_sizes()` never called) shows a dash rather than a misleading zero.

Back to top
