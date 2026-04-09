# WizCLI Bakery Plugin Design

## Overview

A new Bakery plugin that runs `wizcli scan container-image` against each image target in a
Bakery project. The plugin follows the same architecture as the existing `dgoss` plugin:
CLI registration, ToolOptions for bakery.yaml, a command builder, a suite runner, and
lightweight report parsing for a Rich summary table.

## File Structure

```
posit_bakery/plugins/builtin/wizcli/
  __init__.py    # WizCLIPlugin class (register_cli, execute, results)
  command.py     # WizCLICommand Pydantic model (builds wizcli invocation)
  options.py     # WizCLIOptions(ToolOptions) for bakery.yaml
  report.py      # WizScanReport, WizScanReportCollection
  errors.py      # BakeryWizCLIError
  suite.py       # WizCLISuite (runs commands, collects results)
```

Entry point in `pyproject.toml`:

```toml
[project.entry-points."bakery.plugins"]
wizcli = "posit_bakery.plugins.builtin.wizcli:WizCLIPlugin"
```

Test files under `test/plugins/builtin/wizcli/`.

## CLI Surface: `bakery wizcli scan`

### Standard Bakery Filter Options

Inherited from the dgoss pattern: `--context`, `--image-name`, `--image-version`,
`--image-variant`, `--image-os`, `--image-platform`, `--dev-versions`,
`--matrix-versions`, `--metadata-file`.

### WizCLI-Specific Options

| CLI Option | Type | Default | Notes |
|---|---|---|---|
| `--disabled-scanners` | `str` (comma-sep) | None | Passed through to wizcli |
| `--driver` | `str` | None | `extract`, `mount`, `mountWithLayers` |
| `--client-id` | `str` | None | Override for `WIZ_CLIENT_ID` env var |
| `--client-secret` | `str` | None | Override for `WIZ_CLIENT_SECRET` env var |
| `--use-device-code` | `bool` flag | False | Use device code auth flow |
| `--no-browser` | `bool` flag | False | Don't open browser for device code |
| `--timeout` | `str` | None | Scan timeout (e.g., `1h`) |
| `--no-publish` | `bool` flag | False | Don't publish results to Wiz portal |
| `--scan-context-id` | `str` | None | Context identifier (`WIZ_SCAN_CONTEXT_ID`) |
| `--log` | `Path` | None | File path for wizcli debug logs |

All are optional. Authentication falls back to inherited `WIZ_CLIENT_ID` and
`WIZ_CLIENT_SECRET` environment variables from the parent process.

## ToolOptions: `WizCLIOptions`

Configured in `bakery.yaml` at the image or variant level:

```yaml
options:
  - tool: wizcli
    projects:
      - "my-project-slug"
    policies:
      - "policy-id-or-name"
    tags:
      - "team=platform"
      - "env=ci"
    scanOsManagedLibraries: true
    scanGoStandardLibrary: false
```

### Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `tool` | `Literal["wizcli"]` | `"wizcli"` | Discriminator for YAML parsing |
| `projects` | `list[str] \| None` | None | Wiz project IDs or slugs |
| `policies` | `list[str] \| None` | None | Policies to apply |
| `tags` | `list[str] \| None` | None | Tags (KEY or KEY=VALUE) |
| `scanOsManagedLibraries` | `bool \| None` | None | Override tenant setting |
| `scanGoStandardLibrary` | `bool \| None` | None | Override tenant setting |

The `update()` method uses `model_fields_set` for variant-level override semantics,
matching the `GossOptions` pattern.

## WizCLICommand

Built via `WizCLICommand.from_image_target(target, **cli_options)`. Constructs the full
command list:

```
wizcli scan container-image <image_ref>
  --json-output-file=<results_path>
  --dockerfile=<containerfile>
  [--wiz-configuration-file=<path>]         # if .wiz found at version or image level
  [--projects=p1,p2]                        # from ToolOptions
  [--policies=p1,p2]                        # from ToolOptions
  [--tags=k=v,k2=v2]                        # from ToolOptions
  [--scan-os-managed-libraries=true/false]  # from ToolOptions (explicit bool)
  [--scan-go-standard-library=true/false]   # from ToolOptions (explicit bool)
  [--disabled-scanners=...]                 # from CLI
  [--driver=...]                            # from CLI
  [--client-id=...]                         # from CLI
  [--client-secret=...]                     # from CLI
  [--use-device-code]                       # from CLI
  [--no-browser]                            # from CLI
  [--timeout=...]                           # from CLI
  [--no-publish]                            # from CLI
  [--scan-context-id=...]                   # from CLI
  [--log=...]                               # from CLI
  --no-color --no-style                     # always set (machine output)
```

### Logic-Determined Options

- **`--dockerfile`**: Always set to `target.containerfile` (relative path from base_path,
  which is also the `cwd` for the subprocess).
- **`--wiz-configuration-file`**: Search order:
  1. `<version_path>/.wiz` (same directory as Containerfile)
  2. `<image_path>/.wiz` (parent image directory)
  3. Omitted (wizcli uses its own default `.wiz` lookup from CWD)
- **`--json-output-file`**: Set to `results/wizcli/<image_name>/<uid>.json`.
- **`--no-color --no-style`**: Always set for machine-parseable output.
- **`--scan-os-managed-libraries`** and **`--scan-go-standard-library`**: Rendered as
  `=true` or `=false` when explicitly set in ToolOptions. Omitted when None.

### Binary Discovery

Uses `find_bin(base_path, "wizcli", "WIZCLI_PATH")` with fallback to `"wizcli"` (system PATH).

### stdout/stderr Handling

wizcli's stdout/stderr are sent to `subprocess.DEVNULL` by default. When verbose logging
is active, output is captured and logged at debug level instead. This suppresses wizcli's
cluttered human output in favor of Bakery's own log messages.

## WizCLISuite

Follows the `DGossSuite` pattern:

1. Clear and recreate `results/wizcli/` directory.
2. For each `WizCLICommand`:
   a. Log the target being scanned.
   b. Run via `subprocess.run()` with `os.environ.copy()` (inherits `WIZ_*` vars).
   c. wizcli writes results directly via `--json-output-file`.
   d. Parse the JSON results file into `WizScanReport`.
   e. On parse failure with non-zero exit code, create `BakeryWizCLIError`.
3. Return `(WizScanReportCollection, errors)`.

## Report Models

### `WizScanReport`

Lightweight model parsed from the JSON output file. Fields:

- `filepath: Path` — path to the JSON results file
- `scan_id: str` — from top-level `id`
- `status_state: str` — from `status.state` (e.g., `SUCCESS`)
- `status_verdict: str` — from `status.verdict` (e.g., `WARN_BY_POLICY`)
- `report_url: str | None` — from `reportUrl`, only when it's a valid URL
- `critical_count: int` — aggregated from `vulnerableSBOMArtifactsByNameVersion`
- `high_count: int`
- `medium_count: int`
- `low_count: int`
- `info_count: int`

Severity counts are computed by iterating
`result.vulnerableSBOMArtifactsByNameVersion[*].vulnerabilityFindings.severities`
and summing each level.

The `report_url` field is set to None when the value is not a valid URL (wizcli returns
a descriptive string like "This scan did not generate a report in the Wiz portal" when
results are not published).

### `WizScanReportCollection`

Dict subclass keyed `image_name -> {uid: (target, report)}`. Provides:

- `table() -> rich.Table` — columns: Image, Version, Variant, OS, Verdict, Critical,
  High, Medium, Low, Info, Report URL
- `aggregate()` — total severity counts across all targets

## Error Handling

### `BakeryWizCLIError`

Extends `BakeryToolRuntimeError`. Adds no extra fields beyond what the base class
provides. The `__str__` method formats exit code, command executed, and any captured
stderr.

### Exit Code Semantics

| Exit Code | Meaning | Bakery Behavior |
|---|---|---|
| 0 | Passed | Success |
| 1 | General error (timeout, network) | Failure — execution error |
| 2 | Invalid command (bad syntax) | Failure — execution error |
| 3 | Authentication error | Failure — execution error |
| 4 | Policy violation (security issue) | Failure — security issue messaging |

All non-zero exit codes are failures. Exit code 4 receives distinct messaging indicating
a real security issue that must be addressed.

## Results Display

The `results()` method on `WizCLIPlugin`:

1. Reconstructs `WizScanReportCollection` from `ToolCallResult` artifacts.
2. Prints a Rich summary table with per-target severity counts and verdict.
3. For exit code 4 targets: prints a security violation warning with report URL if available.
4. For other non-zero targets: prints execution error details.
5. Raises `typer.Exit(1)` if any target failed.
6. Prints success message if all targets passed.
