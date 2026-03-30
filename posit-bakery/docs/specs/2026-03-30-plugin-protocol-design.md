# Plugin Protocol Design

**Date:** 2026-03-30
**Branch:** `feature/plugin-protocol`
**Scope:** Refactor dgoss as a builtin plugin to validate a generic plugin protocol for Bakery.

## Goals

1. Define a `BakeryToolPlugin` protocol that all tool plugins (builtin and external) implement.
2. Refactor dgoss as the first builtin plugin to validate the protocol end-to-end.
3. Design for future extensibility (external plugins via entry points) without building it yet.

## Decisions

| Question | Decision |
|---|---|
| Primary goal | Both internal modularity and future external extensibility |
| CLI structure | Plugin-namespaced commands (`bakery dgoss run`) |
| Backward compatibility | Deprecation bridge: `bakery run dgoss` warns and delegates |
| Plugin discovery | Python entry points (`bakery.plugins` group) for both builtins and externals |
| Execute return type | `list[ToolCallResult]`, one per target, goss-specific data in `artifacts` |
| Prototype scope | dgoss only — validate before generalizing |
| Architecture approach | Plugin owns everything (self-contained package) |

## Plugin Protocol

```python
class ToolCallResult(BaseModel):
    exit_code: int
    tool_name: str
    target: ImageTarget
    stdout: str
    stderr: str
    artifacts: dict[str, Any] | None = None


class BakeryToolPlugin(Protocol):
    name: str
    description: str

    def register_cli(self, app: typer.Typer) -> None:
        """Register the plugin's own command group with the root Typer app."""
        ...

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        platform: str | None = None,
        **kwargs,
    ) -> list[ToolCallResult]:
        """Execute the plugin's tool against the given targets."""
        ...
```

Changes from the initial draft:
- `execute()` takes `base_path` and `targets` directly instead of `typer.Context`, removing coupling to typer for programmatic callers.
- `execute()` returns `list[ToolCallResult]` with one result per target.
- `platform` is an explicit parameter since it's common across container image tools.

## Plugin Discovery & Registry

### Entry Points

Plugins declare themselves in `pyproject.toml`:

```toml
[project.entry-points."bakery.plugins"]
dgoss = "posit_bakery.plugins.builtin.dgoss:DGossPlugin"
```

This mechanism is the same for builtins and future external plugins.

### Registry

`posit_bakery/plugins/registry.py` provides:

- `discover_plugins() -> dict[str, BakeryToolPlugin]` — loads all plugins from the `bakery.plugins` entry point group, instantiates each, validates protocol conformance, returns `{name: instance}`.
- `get_plugin(name: str) -> BakeryToolPlugin` — retrieves a specific plugin by name, raises if not found.

### CLI Integration

The CLI app's entry point (where the root `typer.Typer` is constructed) calls `discover_plugins()` and iterates over the returned plugins, calling `plugin.register_cli(app)` for each. This happens before `app()` is invoked, so all plugin commands are available at parse time. The dgoss plugin registers a `dgoss` command group with a `run` subcommand.

### Config Decoupling

`BakeryConfig.dgoss_targets()` is updated to look up the dgoss plugin from the registry and call `execute()`. `config.py` no longer imports anything from the goss module directly.

## DGoss Plugin Structure

```
posit_bakery/plugins/builtin/
    __init__.py
    dgoss/
        __init__.py      # DGossPlugin class
        command.py        # DGossCommand model + find_dgoss_bin, find_goss_bin, find_test_path
        suite.py          # DGossSuite execution orchestration
        report.py         # GossJsonReport, GossJsonReportCollection, GossResult, etc.
        errors.py         # BakeryDGossError
```

### DGossPlugin class

- `name = "dgoss"`, `description = "Run Goss tests against container images"`
- `register_cli()` creates a `dgoss` typer group with a `run` subcommand. The subcommand owns the filtering options (`--image-name`, `--image-version`, etc.) currently in `cli/run.py`.
- `execute()` instantiates `DGossSuite`, calls `run()`, converts the `GossJsonReportCollection` and errors into `list[ToolCallResult]`.

### What moves vs. stays

| Code | Destination |
|---|---|
| `DGossCommand`, helpers | `plugins/builtin/dgoss/command.py` |
| `DGossSuite` | `plugins/builtin/dgoss/suite.py` |
| Report models | `plugins/builtin/dgoss/report.py` |
| `BakeryDGossError` | `plugins/builtin/dgoss/errors.py` |
| `BakeryToolRuntimeError` (base) | Stays in `posit_bakery/error.py` |
| `find_bin()` | Stays in `posit_bakery/util.py` |
| Goss tool config in `bakery.yaml` | Stays in `posit_bakery/config/tools/` |
| `posit_bakery/image/goss/` | Removed entirely |

## Deprecation Bridge

The existing `bakery run dgoss` command in `cli/run.py` is replaced with a thin wrapper that:

1. Emits a `DeprecationWarning` via `warnings.warn()`: `"'bakery run dgoss' is deprecated. Use 'bakery dgoss run' instead."`
2. Delegates to the dgoss plugin's `execute()` via the registry.
3. Passes through all CLI options so existing invocations keep working.

A future release removes the wrapper entirely.

## Test Migration

### Test location

Tests move from `test/image/goss/` to `test/plugins/builtin/dgoss/`:

```
test/plugins/builtin/dgoss/
    __init__.py
    test_command.py     # DGossCommand tests (from test_dgoss.py)
    test_suite.py       # DGossSuite tests (from test_dgoss.py)
    test_report.py      # Report tests (from test_report.py)
```

### New tests

- `test/plugins/test_registry.py` — tests for `discover_plugins()` and `get_plugin()`, verifying dgoss is discoverable via entry points.
- Plugin protocol conformance test — verifies `DGossPlugin` satisfies `BakeryToolPlugin` using `runtime_checkable`.
- Deprecation bridge test — verifies `bakery run dgoss` emits a warning.

### Existing test behavior

Tests validate the same logic from the new module paths. No new test logic needed for the moved code.

## File Change Summary

### New files

- `posit_bakery/plugins/registry.py`
- `posit_bakery/plugins/builtin/__init__.py`
- `posit_bakery/plugins/builtin/dgoss/__init__.py`
- `posit_bakery/plugins/builtin/dgoss/command.py`
- `posit_bakery/plugins/builtin/dgoss/suite.py`
- `posit_bakery/plugins/builtin/dgoss/report.py`
- `posit_bakery/plugins/builtin/dgoss/errors.py`
- `test/plugins/__init__.py`
- `test/plugins/builtin/__init__.py`
- `test/plugins/builtin/dgoss/__init__.py`
- `test/plugins/builtin/dgoss/test_command.py`
- `test/plugins/builtin/dgoss/test_suite.py`
- `test/plugins/builtin/dgoss/test_report.py`
- `test/plugins/test_registry.py`

### Modified files

- `posit_bakery/plugins/protocol.py` — updated protocol signature
- `pyproject.toml` — add `bakery.plugins` entry point
- CLI app setup — call `discover_plugins()` and `register_cli()` at startup
- `posit_bakery/cli/run.py` — replace `dgoss` command body with deprecation wrapper
- `posit_bakery/config/config.py` — remove direct dgoss imports, use plugin registry
- `posit_bakery/error.py` — remove `BakeryDGossError`

### Removed files

- `posit_bakery/image/goss/__init__.py`
- `posit_bakery/image/goss/dgoss.py`
- `posit_bakery/image/goss/report.py`
- `test/image/goss/__init__.py`
- `test/image/goss/test_dgoss.py`
- `test/image/goss/test_report.py`
