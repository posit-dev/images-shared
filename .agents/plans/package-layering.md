# Split BakeryConfig into config, targets, and build layers

Cut `posit_bakery/config/config.py` so that `config/` stops importing the
execution layer. No existing packages or files are renamed or moved; two new
packages (`targets/`, `build/`) and two new modules are added.

## Problem

`config/config.py` imports `image.bake`, `image.image_target`, `parallel`,
`registry_management.ghcr`, and `settings`. `image/image_target.py` imports
nine `config.*` modules back. `config/tools/__init__.py` imports
`config.config`. Eight `# avoid circular import` local imports work around
the cycle.

The cause is `BakeryConfig` doing five jobs:

| Responsibility | Methods | Layer |
|---|---|---|
| Load + validate bakery.yaml | `__init__`, `from_context` | config |
| Write bakery.yaml + scaffold dirs | `write`, `new`, `_get_*_index`, `create_*`, `remove_*`, `patch_version`, `rerender_files` | config |
| Select build targets | `generate_image_targets`, `apply_recent_versions`, `version_matches`, `_apply_dev_spec`, `BakerySettings`, `BakeryConfigFilter` | transformation |
| Execute builds | `build_targets`, `bake_plan_targets`, `_retry_build`, `load_build_metadata_from_file`, `_merge_sequential_build_metadata_files` | execution |
| Clean registries | `clean_caches`, `clean_temporary` | execution |

The last three are why `config/` imports `image/`, `parallel/`, and
`registry_management/`. The first two stay; they both own the file.

Secondary: `cli/ci.py::matrix` (~150 lines) re-implements the
version/dev/matrix/recent filtering loop from `generate_image_targets`.

### Not in scope

Recorded so the reasoning is not lost. Each is independent, 3–10 files, and
cosmetic relative to the cycle.

- Extract mutations (`create_*`, `remove_*`, `patch_version`, `write`, `new`) to a `project/` package. All their imports are already inside `config/`; splitting them buys cohesion, not layering.
- Move network resolvers (`config/dependencies/{python,r,quarto,positron}.py`, `config/image/posit_product/`, dev-version channel fetch) to `resolve/`.
- Move `render_files` off `ImageVersion`/`ImageMatrix` into `render/`.
- Move `ImageTarget.build()`/`.remove()` and `BakePlan.build()` into `build/docker.py`.
- Split builtin plugin `__init__.py` files (300–550 lines of typer bodies) into `cli.py` + class.
- Rename `config/`→`schema/`, `image/`→`targets/`+`build/`, `registry_management/`→`registry/`. Touches ~95 source and ~80 test files for naming alone. Rejected.
- Delete empty `services/`.

### External surface

No sibling repo imports `posit_bakery` Python modules (checked
`images-connect`, `images-workbench`, `images-package-manager`,
`images-examples`). Public surface is the `bakery` CLI, the `bakery.plugins`
entry-point protocol, and the `bakery.yaml` schema. None are affected.

## Target structure

```
posit_bakery/
├── config/
│   ├── config.py                ~690 lines (was 1366): BakeryConfig loader + BakeryConfigDocument + mutations
│   ├── settings.py        NEW   BakerySettings, BakeryConfigFilter
│   └── image/parsed_version.py  + version_matches (shared by rerender_files and selection)
│
├── targets/               NEW   config → list[ImageTarget]. Pure.
│   ├── __init__.py
│   ├── selection.py             select_targets(config, settings) -> list[ImageTarget]
│   │                            apply_recent_versions, _apply_dev_spec, _extract_calver_minor,
│   │                            settings-conflict warnings (from BakeryConfig.__init__),
│   │                            exit_if_no_targets, _describe_active_filters (from cli/common.py)
│   └── ci_matrix.py             matrix_rows(targets, exclude) -> list[dict]
│
├── build/                 NEW   execution orchestration
│   ├── __init__.py
│   └── runner.py                build_targets(base_path, targets, settings, ...) -> BuildResult
│                                bake_plan_json, _retry_build, load/merge build metadata
│
└── registry_management/
    └── clean.py           NEW   clean_caches(targets, ...), clean_temporary(targets, ...)
```

Everything else is unchanged except import lines and call sites.

### Dependency rule after the split

```
cli, plugins          → build, targets, registry_management, config, image, parallel
build                 → targets, image, parallel, config
targets               → config, image
registry_management   → image
image                 → config, parallel
config                → config, const, error, util, settings
```

`config` no longer imports `image.bake`, `parallel`, or
`registry_management`. `image → config` remains; that direction is fine once
`config` stops importing `image`.

### API shape

Before:

```python
c = BakeryConfig.from_context(context, settings)
c.build_targets(strategy=..., push=...)
uids = c.last_build_succeeded_uids
```

After:

```python
c = BakeryConfig.from_context(context, settings)   # load, validate, resolve dev versions
targets = select_targets(c, settings)              # targets.selection
result = build_targets(c.base_path, targets, settings, strategy=..., push=...)  # build.runner
uids = result.succeeded_uids
```

- `BakeryConfig.targets` and `get_image_target_by_uid` are removed; callers hold the list.
- `BakeryConfig.settings` stays (needed to know whether dev versions were loaded).
- `BakerySettings`/`BakeryConfigFilter` are re-exported from `config.config` for one release, then removed.

## Phases

Each phase is one PR and keeps `uv run pytest` green.

### Phase 1 — `build/runner.py`, `registry_management/clean.py`

Cut `_retry_build`, `build_targets`, `bake_plan_targets`,
`load_build_metadata_from_file`, `_merge_sequential_build_metadata_files`,
`clean_caches`, `clean_temporary` out of `config.py`. Add a `BuildResult`
dataclass (`succeeded_uids: set[str] | None`) replacing the
`last_build_succeeded_uids` attribute.

- New: `build/__init__.py`, `build/runner.py`, `registry_management/clean.py`
- Edited: `config/config.py`, `cli/build.py`, `cli/clean.py`, `cli/ci.py`, `plugins/builtin/imagetools/imagetools.py`
- Tests: `test/config/test_config.py` — patch target `posit_bakery.config.config.time.sleep` → `posit_bakery.build.runner.time.sleep`; move build/clean tests to `test/build/test_runner.py`, `test/registry_management/test_clean.py`
- Result: `config/` no longer imports `image.bake`, `parallel`, `registry_management`. Cycle broken.

### Phase 2 — `targets/selection.py`, `targets/ci_matrix.py`, `config/settings.py`

Move `generate_image_targets` → `select_targets(config, settings)`. Move
`BakerySettings`/`BakeryConfigFilter` to `config/settings.py`. Move
`version_matches` to `config/image/parsed_version.py`. Move
`exit_if_no_targets` + `_describe_active_filters` from `cli/common.py`.
Rewrite `cli/ci.py::matrix` to `select_targets` + `matrix_rows`; delete the
duplicate loop.

- New: `targets/__init__.py`, `targets/selection.py`, `targets/ci_matrix.py`, `config/settings.py`
- Edited: `config/config.py`, `config/image/parsed_version.py`, `cli/common.py`, `cli/ci.py`, `cli/build.py`, `cli/get.py`, `cli/run.py`, `cli/clean.py`, 4 plugin `__init__.py` / `imagetools.py`
- Tests: ~6 files importing from `config.config`; move selection tests to `test/targets/test_selection.py`; add a test asserting `matrix_rows(select_targets(...))` equals current `ci matrix` output for each fixture under `test/cli/testdata/ci/matrix/`
- Result: `config.py` is loader + document + mutations. `ci matrix` and `build` share one filter.

### Phase 3 — enforce

Add `import-linter` to pre-commit with one contract: `posit_bakery.config`
may not import `posit_bakery.image`, `posit_bakery.build`,
`posit_bakery.targets`, `posit_bakery.parallel`,
`posit_bakery.registry_management`, `posit_bakery.plugins`,
`posit_bakery.cli`. Remove the now-dead `# avoid circular import` local
imports in `config/config.py` and `config/tools/__init__.py`. Change
`ToolCallResult.target: Any` to `ImageTarget`.

- Edited: `.pre-commit-config.yaml`, `pyproject.toml`, `config/config.py`, `config/tools/__init__.py`, `plugins/protocol.py`

## Size

### Files that change size

| File | Now | After | Δ |
|---|---|---|---|
| `config/config.py` | 1366 | ~690 | −680 |
| `cli/ci.py` | 734 | ~600 | −130 |
| `cli/common.py` | 203 | ~160 | −40 |
| `config/image/parsed_version.py` | 177 | ~210 | +30 |
| `targets/selection.py` | — | ~330 | +330 |
| `targets/ci_matrix.py` | — | ~40 | +40 |
| `config/settings.py` | — | ~135 | +135 |
| `build/runner.py` | — | ~190 | +190 |
| `registry_management/clean.py` | — | ~60 | +60 |
| 2 × `__init__.py` | — | ~5 | +10 |

Whole package: 19684 → ~19630. Largest file: `config.py` 1366 →
`imagetools.py` 775 (unchanged).

### Moved vs changed (excluding import lines)

| Block | Relocated | Changed | Verbatim |
|---|---|---|---|
| `BakerySettings` + `BakeryConfigFilter` | 126 | 0 | 126 |
| Module-level funcs (`_retry_build`, `apply_recent_versions`, `version_matches`, `_apply_dev_spec`, `_extract_calver_minor`) | 162 | ~2 | 160 |
| `generate_image_targets` → `select_targets` | 153 | ~6 | ~147 |
| `__init__` settings-conflict warnings | 34 | ~12 | ~22 |
| `build_targets` | 111 | ~12 | ~99 |
| `bake_plan_targets`, metadata load/merge | 38 | ~4 | ~34 |
| `clean_caches`, `clean_temporary` | 52 | ~3 | ~49 |
| `exit_if_no_targets` + `_describe_active_filters` | 42 | ~3 | ~39 |
| **Total relocated** | **718** | **~42** | **~676** |

Changes inside moved blocks are `self.X` → parameter, signatures, and
`self.targets = ...` / `self.last_build_succeeded_uids = ...` → return values.

Not moved:

| | Lines |
|---|---|
| New: `matrix_rows()`, `BuildResult`, `__init__.py` files | ~60 |
| Rewritten: `cli/ci.py::matrix` body | ~25 written, ~150 deleted |
| Call-site edits, ~17 source files | ~30 |
| Test call-site / patch-target edits, ~10 files | ~40 |

Method → function dedent will make `git diff` show ~260 changed lines for
`select_targets` and `build_targets`; use `git diff -w --color-moved` to see
the real ~40.

## Risks

- **Patch targets in tests.** `test/config/test_config.py` patches
  `posit_bakery.config.config.time.sleep` (called out in the `_retry_build`
  docstring). Grep `test/` for `posit_bakery.config.config.` before each
  phase.
- **`BakeryConfig.targets` consumers.** Plugins and `cli/get.py` read
  `c.targets` directly. Each becomes `select_targets(c, settings)`; the
  result must be computed once per command and passed down, not recomputed.
- **Behavioural equivalence of `ci matrix`.** The duplicated loop has
  drifted from `generate_image_targets` in places (changeset filtering,
  `--exclude` field handling, `--recent` warnings). Write the equivalence
  test against current output *before* rewriting, and treat any diff as a
  decision to make, not a bug to paper over.
- **`--dev-spec` ordering.** `_apply_dev_spec` mutates dev-version models
  and must run before `image.load_dev_versions()` in `BakeryConfig.__init__`.
  It moves to `targets/selection.py` but is still called from the loader.
  That is a `config → targets` import — the one exception. Alternative:
  leave `_apply_dev_spec` and `_extract_calver_minor` (74 lines) in
  `config.py`, since they mutate config models, not targets. Recommended.

## Open questions

- `config/settings.py` collides in name with top-level `settings.py`
  (env-driven `SETTINGS`). Alternative: `config/options.py`.
- Should `BakeryConfig` keep a convenience `select_targets()` method
  delegating to `targets.selection`? Reduces churn in ~10 callers but keeps
  `config → targets`. Recommendation: no.
