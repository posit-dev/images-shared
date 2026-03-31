# ORAS Plugin Design

## Summary

Refactor the ORAS code from `posit_bakery/image/oras/` into a builtin plugin at
`posit_bakery/plugins/builtin/oras/`, following the same pattern established by the dgoss
plugin. The `bakery ci merge` command is refactored to delegate to the oras plugin instead
of calling `OrasMergeWorkflow` directly through `config.merge_targets()`.

## Goals

- ORAS becomes a first-class plugin implementing `BakeryToolPlugin`
- New `bakery oras merge` CLI command for direct invocation
- `bakery ci merge` delegates to the oras plugin (no workflow duplication)
- `config.merge_targets()` is removed; the plugin owns the workflow
- No `tool_options_class` (ORAS remains config-free for now)

## Non-goals

- Exposing low-level ORAS subcommands (`copy`, `delete`) as CLI commands
- Adding ORAS-specific options to `bakery.yaml`

## File structure

```
posit_bakery/plugins/builtin/oras/
  __init__.py      # OrasPlugin class
  oras.py          # Moved from image/oras/oras.py (ORAS commands + workflow models)
```

The old `posit_bakery/image/oras/` directory is deleted.

## OrasPlugin class

```python
class OrasPlugin(BakeryToolPlugin):
    name: str = "oras"
    description: str = "Merge multi-platform images using ORAS"
```

No `tool_options_class`.

### `register_cli(app)`

Creates an `oras` command group with a `merge` subcommand. The `merge` command accepts:

- `metadata_file: list[Path]` (argument) - paths to build metadata JSON files
- `--context` - root path (defaults to cwd)
- `--temp-registry` - temporary registry for staging indexes
- `--dry-run` - log commands without executing

The command:
1. Loads `BakeryConfig` with settings (dev/matrix versions included, temp_registry)
2. Resolves glob patterns in metadata file arguments
3. Loads build metadata from files via `config.load_build_metadata_from_file()`
4. Calls `plugin.execute(base_path, targets, temp_registry=temp_registry, dry_run=dry_run)`
5. Calls `plugin.display_results(results)`

### `execute(base_path, targets, **kwargs)`

Accepts `temp_registry` and `dry_run` via kwargs. Iterates over targets:

1. Skips targets without merge sources (`target.get_merge_sources()` is empty)
2. Validates `temp_registry` is set on the target settings
3. Creates `OrasMergeWorkflow.from_image_target(target)`
4. Runs the workflow
5. Returns a `ToolCallResult` per processed target:
   - `exit_code`: 0 on success, 1 on failure
   - `tool_name`: "oras"
   - `target`: the ImageTarget
   - `stdout`/`stderr`: captured from workflow
   - `artifacts`: `{"workflow_result": OrasMergeWorkflowResult}`

Targets skipped (no merge sources) do not produce a `ToolCallResult`.

Targets that fail validation (missing `temp_registry`) produce a `ToolCallResult` with
`exit_code=1` and the error message in `stderr`.

### `display_results(results)`

Iterates over results and:
- Logs successful merges with destination info from the workflow result artifact
- Logs errors for failed results
- If any results have `exit_code != 0`, calls `raise typer.Exit(code=1)`
- On all success, prints a success message

## `bakery ci merge` refactoring

The `merge` command in `cli/ci.py` is refactored to:

1. Keep its existing argument parsing (metadata files, context, temp-registry, dry-run)
2. Load config and metadata files as before
3. Instead of calling `config.merge_targets()`, get the oras plugin:
   ```python
   from posit_bakery.plugins.registry import get_plugin
   oras = get_plugin("oras")
   results = oras.execute(config.base_path, config.targets, dry_run=dry_run)
   oras.display_results(results)
   ```
4. The post-merge `docker buildx imagetools inspect` verification (line 1027 of
   `config.py`) stays in `ci merge` as a CI-specific sanity check. It runs after
   `oras.execute()` returns, using the workflow result artifacts to get the first
   destination tag. `bakery oras merge` does not perform this verification.

`config.merge_targets()` in `config.py` is removed.

## ORAS module (`oras.py`)

The existing code from `image/oras/oras.py` moves to `plugins/builtin/oras/oras.py` with
no functional changes. All classes remain:

- `find_oras_bin(context)` - binary discovery
- `get_repository_from_ref(ref)` - reference parsing
- `OrasCommand` - abstract base for CLI commands
- `OrasManifestIndexCreate` - manifest index creation
- `OrasCopy` - cross-registry copy
- `OrasManifestDelete` - manifest deletion
- `OrasMergeWorkflowResult` - workflow result model
- `OrasMergeWorkflow` - merge orchestrator

## Entry point registration

In `pyproject.toml`:

```toml
[project.entry-points."bakery.plugins"]
dgoss = "posit_bakery.plugins.builtin.dgoss:DGossPlugin"
oras = "posit_bakery.plugins.builtin.oras:OrasPlugin"
```

## Import updates

All imports of `posit_bakery.image.oras` across the codebase change to
`posit_bakery.plugins.builtin.oras.oras`. The primary callsite is `config.py`'s
`merge_targets()` which is being removed, so most import changes are in tests.

## Tests

- Move `test/image/oras/test_oras.py` to `test/plugins/builtin/oras/test_oras.py`
- Update imports to the new module path
- Add new tests for `OrasPlugin`:
  - `test_execute_success` - workflow runs and returns ToolCallResults
  - `test_execute_skips_targets_without_sources` - targets without merge sources are skipped
  - `test_execute_missing_temp_registry` - returns error result
  - `test_execute_dry_run` - dry run mode passes through
  - `test_display_results_success` - prints success
  - `test_display_results_with_errors` - exits with code 1
- Update `test/cli/test_ci.py` to reflect delegation to plugin

## Migration checklist

1. Create `posit_bakery/plugins/builtin/oras/__init__.py` with `OrasPlugin`
2. Move `posit_bakery/image/oras/oras.py` to `posit_bakery/plugins/builtin/oras/oras.py`
3. Delete `posit_bakery/image/oras/`
4. Add entry point in `pyproject.toml`
5. Refactor `cli/ci.py` `merge` command to use plugin
6. Remove `config.merge_targets()` from `config.py`
7. Update all imports
8. Move and update tests
9. Run `just install && just test` to verify
