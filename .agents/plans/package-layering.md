# Package layering for posit_bakery

Split `config/config.py` (`BakeryConfig`, 1366 lines) into its constituent
responsibilities so that the config layer no longer imports the execution
layer. No existing packages are renamed; new packages are added alongside.

## Current state

~19.7k lines, 108 source files. The nominal split is `config/` (models) →
`image/` (targets, bake) → `cli/`, with `plugins/`, `parallel/`,
`registry_management/` alongside.

### Structural defect

`config/config.py` imports `image.bake`, `image.image_target`, `parallel`,
`registry_management.ghcr`, and `settings`. `image/image_target.py` imports
nine `config.*` modules back. `config/tools/__init__.py` imports
`config.config`. Eight `# avoid circular import` local imports work around
the resulting cycle.

The cause is that `BakeryConfig` does five unrelated jobs:

| Responsibility | Methods |
|---|---|
| Load + validate bakery.yaml | `__init__`, `from_context` |
| ruamel round-trip write + scaffolding | `write`, `new`, `_get_image_index`, `_get_version_index`, `create_image`, `remove_image`, `create_version`, `patch_version`, `create_matrix`, `remove_version`, `rerender_files` |
| Select build targets | `generate_image_targets`, `get_image_target_by_uid`, module-level `apply_recent_versions`, `version_matches`, `BakerySettings`, `BakeryConfigFilter`, `_apply_dev_spec` |
| Execute builds | `build_targets`, `bake_plan_targets`, `_retry_build`, `load_build_metadata_from_file`, `_merge_sequential_build_metadata_files`, `last_build_succeeded_uids` |
| Clean registries | `clean_caches`, `clean_temporary` |

Only the first is a config concern. The last two are why `config/` imports
`image/`, `parallel/`, and `registry_management/`.

### Secondary duplication

`cli/ci.py::matrix` (lines ~290–400) re-implements the
version/dev/matrix/recent filtering loop from
`BakeryConfig.generate_image_targets`. The two can drift.

### Other untidiness, not addressed here

Network I/O in `config/dependencies/` and `config/image/posit_product/`;
Jinja rendering on `ImageVersion`/`ImageMatrix`; `ImageTarget.build()` and
`BakePlan.build()` on data models; plugins importing `cli.common`;
`config/image/` vs `image/` naming; empty `services/`. These are cosmetic
relative to the cycle and each would move 3–10 files. Listed under
"Deferred" so they are not lost, but out of scope.

### External surface

No sibling repo imports `posit_bakery` Python modules (checked
`images-connect`, `images-workbench`, `images-package-manager`,
`images-examples`). Public surface is the `bakery` CLI, the `bakery.plugins`
entry-point protocol, and the `bakery.yaml` schema. None are affected.

## Proposed structure

Existing packages unchanged. Three new packages; `config/config.py` shrinks
to the loader.

```
posit_bakery/
├── config/                 (unchanged, except config.py shrinks)
│   ├── config.py               BakeryConfig: load, validate, resolve dev versions,
│   │                           hold `model` + `_config_yaml`. ~200 lines.
│   ├── settings.py       NEW   BakerySettings, BakeryConfigFilter (moved from config.py;
│   │                           they are config-layer inputs, not selection logic)
│   └── ...                     everything else as-is
│
├── project/                NEW  bakery.yaml mutation + scaffolding
│   ├── __init__.py
│   ├── store.py                write(), _get_image_index, _get_version_index
│   ├── scaffold.py             new(), create_image_files_template
│   └── mutations.py            create_image, remove_image, create_version,
│                               patch_version, create_matrix, remove_version,
│                               rerender_files
│
├── targets/                NEW  config → ImageTarget list (pure)
│   ├── __init__.py
│   ├── selection.py            select_targets(config, settings) -> list[ImageTarget]
│   │                           apply_recent_versions, version_matches, _apply_dev_spec,
│   │                           uid-duplicate check, exit_if_no_targets (from cli/common.py)
│   └── ci_matrix.py            matrix_rows(targets, exclude) -> list[dict]
│                               replaces the inline loop in cli/ci.py
│
├── build/                  NEW  execution orchestration
│   ├── __init__.py
│   └── runner.py               build_targets(base_path, targets, settings, ...) -> BuildResult
│                               bake_plan_json, _retry_build, metadata load/merge
│
├── registry_management/    (unchanged)
│   └── clean.py          NEW   clean_caches(targets, ...), clean_temporary(targets, ...)
│
├── image/, parallel/, plugins/, cli/   (unchanged; import edits only)
```

### Dependency rule after the split

```
cli, plugins          → build, project, targets, registry_management, config, image, parallel, core*
build                 → targets, image, parallel, config
project               → config, image (for ImageVersion/ImageMatrix render_files)
targets               → config, image
registry_management   → image (ImageTarget for cache names; already true via readme.py)
config                → config only (+ const, error, util, settings)
image                 → config, parallel
```

`config` no longer imports `image.bake`, `parallel`, or
`registry_management`. `image → config` remains (ImageTarget is built from
config models); that direction is fine and not a cycle once `config` stops
importing `image`.

\* "core" = existing top-level `const.py`, `error.py`, `settings.py`,
`log.py`, `util.py`, `retry.py`. Not moved.

### API shape

Before:

```python
c = BakeryConfig.from_context(context, settings)
c.build_targets(strategy=..., push=...)
c.create_version("workbench", "2026.05.0")
```

After:

```python
c = BakeryConfig.from_context(context, settings)       # loads, validates, resolves dev versions
targets = select_targets(c, settings)                  # targets/selection.py
result = build_targets(c.base_path, targets, settings, strategy=..., push=...)  # build/runner.py
create_version(c, "workbench", "2026.05.0")            # project/mutations.py
```

- `BakeryConfig.targets` attribute is removed; callers hold the list.
- `last_build_succeeded_uids` becomes `result.succeeded_uids`.
- `BakeryConfig.settings` stays (needed to know whether dev versions were loaded).

## Phases

Each phase is one PR, keeps `uv run pytest` green, and moves zero existing
files.

### Phase 1 — `build/runner.py` and `registry_management/clean.py`

Cut `build_targets`, `bake_plan_targets`, `_retry_build`,
`load_build_metadata_from_file`, `_merge_sequential_build_metadata_files`,
`clean_caches`, `clean_temporary` out of `config.py`.

- New: 2 modules (+2 `__init__.py`)
- Edited: `config/config.py`, `cli/build.py`, `cli/clean.py`, `cli/ci.py`, `plugins/builtin/imagetools/imagetools.py`
- Tests: `test/config/test_config.py` (patch target `posit_bakery.config.config.time.sleep` → `posit_bakery.build.runner.time.sleep`), new `test/build/test_runner.py`
- Result: `config/` no longer imports `image.bake`, `parallel`, `registry_management`. Cycle broken.

### Phase 2 — `targets/selection.py`, `targets/ci_matrix.py`, `config/settings.py`

Move `generate_image_targets` → `select_targets(config, settings)`. Move
`BakerySettings`/`BakeryConfigFilter` to `config/settings.py` (keep re-export
from `config.config` for one release). Move `exit_if_no_targets` from
`cli/common.py`. Rewrite `cli/ci.py::matrix` to `select_targets` +
`matrix_rows`.

- New: 3 modules
- Edited: `config/config.py`, `cli/common.py`, `cli/ci.py`, `cli/build.py`, `cli/get.py`, `cli/run.py`, `cli/clean.py`, 4 plugin `__init__.py`
- Tests: ~6 files that import from `config.config`; add a test asserting `ci matrix` rows equal the flattened `select_targets` output for each fixture in `test/cli/testdata/ci/matrix/`
- Result: `config.py` is now loader + dev-version resolution + mutations. `ci matrix` and `build` cannot drift.

### Phase 3 — `project/`

Move `write`, `new`, index helpers, `create_image_files_template`, and the
six mutation methods.

- New: 3 modules
- Edited: `config/config.py`, `cli/create.py`, `cli/remove.py`, `cli/update.py`
- Tests: `test/config/test_config.py` split; new `test/project/`
- Result: `config.py` ≈ 200 lines. `BakeryConfigDocument` loses `create_image_files_template`/`create_image_model`.

### Phase 4 — enforce

Add `import-linter` to pre-commit with one contract: `posit_bakery.config`
may not import `posit_bakery.image`, `posit_bakery.build`,
`posit_bakery.targets`, `posit_bakery.project`, `posit_bakery.parallel`,
`posit_bakery.registry_management`, `posit_bakery.plugins`,
`posit_bakery.cli`. Remove the now-dead `# avoid circular import` local
imports in `config/config.py` and `config/tools/__init__.py`.

## Totals

| | Files moved | New modules | Source files edited | Test files edited |
|---|---|---|---|---|
| Phase 1 | 0 | 2 | 5 | 2 |
| Phase 2 | 0 | 3 | 11 | ~6 |
| Phase 3 | 0 | 3 | 4 | ~2 |
| Phase 4 | 0 | 0 | 2 | 0 |
| **Total** | **0** | **8** | **~20** | **~10** |

## Deferred (not in scope)

Recorded so the reasoning isn't lost. Each is independent and 3–10 files.

- Move network resolvers (`config/dependencies/{python,r,quarto,positron}.py`, `config/image/posit_product/`, dev-version channel fetch) to a `resolve/` package.
- Move `render_files` off `ImageVersion`/`ImageMatrix` into a `render/` package.
- Move `ImageTarget.build()`/`.remove()` and `BakePlan.build()` into `build/docker.py`.
- Split builtin plugin `__init__.py` files (300–550 lines of typer bodies) into `cli.py` + class.
- Delete empty `services/`.
- `ToolCallResult.target: Any` → `ImageTarget` once the cycle is gone (can be done in Phase 4 if `plugins.protocol` importing `image.image_target` is clean by then — it already is).

## Open questions

- `config/settings.py` vs leaving `BakerySettings` in `config/config.py`. The
  name collides with top-level `settings.py` (env-driven runtime settings).
  Alternative: `config/options.py`.
- Should `BakeryConfig` keep a convenience `select_targets()` method that
  delegates to `targets.selection`? Reduces churn in ~10 callers but keeps a
  `config → targets` import. Recommendation: no; the whole point is that
  `config` stops knowing about targets.
