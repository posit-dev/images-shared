# ORAS Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the ORAS module into a builtin plugin following the dgoss plugin pattern, with its own `bakery oras merge` CLI command, and refactor `bakery ci merge` to delegate to it.

**Architecture:** Move `posit_bakery/image/oras/` to `posit_bakery/plugins/builtin/oras/`. Create `OrasPlugin` implementing `BakeryToolPlugin` with `register_cli()` and `execute()`. Refactor `bakery ci merge` to use the plugin instead of `config.merge_targets()`, then remove `merge_targets()`.

**Tech Stack:** Python, Pydantic, Typer, pytest, ORAS CLI

---

### Task 1: Move ORAS module to plugin directory

**Files:**
- Move: `posit_bakery/image/oras/oras.py` -> `posit_bakery/plugins/builtin/oras/oras.py`
- Delete: `posit_bakery/image/oras/__init__.py`
- Delete: `posit_bakery/image/oras/` (directory)

- [ ] **Step 1: Create the plugin directory and move the oras module**

```bash
mkdir -p posit-bakery/posit_bakery/plugins/builtin/oras
cp posit-bakery/posit_bakery/image/oras/oras.py posit-bakery/posit_bakery/plugins/builtin/oras/oras.py
```

- [ ] **Step 2: Update the internal import path in `oras.py`**

No changes needed — `oras.py` imports from `posit_bakery.error`, `posit_bakery.image.image_target`, and `posit_bakery.util`, none of which are relative to its old location.

- [ ] **Step 3: Delete the old `posit_bakery/image/oras/` directory**

```bash
rm -rf posit-bakery/posit_bakery/image/oras/
```

- [ ] **Step 4: Verify no remaining imports of the old module path**

```bash
cd posit-bakery && grep -r "from posit_bakery.image.oras" --include="*.py" posit_bakery/
```

Expected: no matches (the `config.py` import will be fixed in Task 5).

- [ ] **Step 5: Commit**

```bash
git add -A posit-bakery/posit_bakery/image/oras posit-bakery/posit_bakery/plugins/builtin/oras/oras.py
git commit -m "refactor: move oras module to plugins/builtin/oras"
```

---

### Task 2: Create OrasPlugin with execute()

**Files:**
- Create: `posit_bakery/plugins/builtin/oras/__init__.py`

- [ ] **Step 1: Write the test for OrasPlugin.execute()**

Create `posit-bakery/test/plugins/builtin/oras/__init__.py` (empty) and `posit-bakery/test/plugins/builtin/oras/test_oras_plugin.py`:

```python
"""Tests for the OrasPlugin."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from posit_bakery.image.image_target import ImageTarget, ImageTargetContext, ImageTargetSettings, StringableList
from posit_bakery.plugins.builtin.oras import OrasPlugin
from posit_bakery.plugins.builtin.oras.oras import OrasMergeWorkflowResult
from posit_bakery.plugins.protocol import BakeryToolPlugin

pytestmark = [pytest.mark.unit]


@pytest.fixture
def plugin():
    return OrasPlugin()


@pytest.fixture
def mock_target_with_sources():
    """Create a mock ImageTarget with merge sources."""
    mock_target = MagicMock(spec=ImageTarget)
    mock_target.image_name = "test-image"
    mock_target.uid = "test-image-1-0-0"
    mock_target.temp_registry = "ghcr.io/posit-dev"
    mock_target.context = MagicMock(spec=ImageTargetContext)
    mock_target.context.base_path = Path("/project")
    mock_target.settings = MagicMock(spec=ImageTargetSettings)
    mock_target.settings.temp_registry = "ghcr.io/posit-dev"
    mock_target.get_merge_sources.return_value = [
        "ghcr.io/posit-dev/test/tmp@sha256:amd64digest",
        "ghcr.io/posit-dev/test/tmp@sha256:arm64digest",
    ]
    mock_target.labels = {"org.opencontainers.image.title": "Test Image"}

    mock_tag = MagicMock()
    mock_tag.destination = "ghcr.io/posit-dev/test-image"
    mock_tag.suffix = "1.0.0"
    mock_tag.__str__ = lambda self: "ghcr.io/posit-dev/test-image:1.0.0"
    mock_target.tags = StringableList([mock_tag])

    return mock_target


@pytest.fixture
def mock_target_without_sources():
    """Create a mock ImageTarget without merge sources."""
    mock_target = MagicMock(spec=ImageTarget)
    mock_target.image_name = "no-sources"
    mock_target.uid = "no-sources-1-0-0"
    mock_target.get_merge_sources.return_value = []
    return mock_target


class TestOrasPluginProtocol:
    def test_implements_protocol(self, plugin):
        assert isinstance(plugin, BakeryToolPlugin)

    def test_name(self, plugin):
        assert plugin.name == "oras"

    def test_description(self, plugin):
        assert plugin.description == "Merge multi-platform images using ORAS"


class TestOrasPluginExecute:
    def test_execute_success(self, plugin, mock_target_with_sources):
        with (
            patch("posit_bakery.plugins.builtin.oras.oras.find_oras_bin", return_value="oras"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
            results = plugin.execute(
                Path("/project"),
                [mock_target_with_sources],
            )

        assert len(results) == 1
        assert results[0].exit_code == 0
        assert results[0].tool_name == "oras"
        assert results[0].target is mock_target_with_sources
        assert results[0].artifacts["workflow_result"].success is True

    def test_execute_skips_targets_without_sources(self, plugin, mock_target_without_sources):
        results = plugin.execute(
            Path("/project"),
            [mock_target_without_sources],
        )

        assert len(results) == 0

    def test_execute_missing_temp_registry(self, plugin, mock_target_with_sources):
        mock_target_with_sources.settings.temp_registry = None

        results = plugin.execute(
            Path("/project"),
            [mock_target_with_sources],
        )

        assert len(results) == 1
        assert results[0].exit_code == 1
        assert "temp_registry" in results[0].stderr

    def test_execute_workflow_failure(self, plugin, mock_target_with_sources):
        with (
            patch("posit_bakery.plugins.builtin.oras.oras.find_oras_bin", return_value="oras"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=1, stdout=b"", stderr=b"create failed"
            )
            results = plugin.execute(
                Path("/project"),
                [mock_target_with_sources],
            )

        assert len(results) == 1
        assert results[0].exit_code == 1
        assert results[0].artifacts["workflow_result"].success is False

    def test_execute_dry_run(self, plugin, mock_target_with_sources):
        with (
            patch("posit_bakery.plugins.builtin.oras.oras.find_oras_bin", return_value="oras"),
            patch("subprocess.run") as mock_run,
        ):
            results = plugin.execute(
                Path("/project"),
                [mock_target_with_sources],
                dry_run=True,
            )

        mock_run.assert_not_called()
        assert len(results) == 1
        assert results[0].exit_code == 0
        assert results[0].artifacts["workflow_result"].success is True

    def test_execute_mixed_targets(self, plugin, mock_target_with_sources, mock_target_without_sources):
        with (
            patch("posit_bakery.plugins.builtin.oras.oras.find_oras_bin", return_value="oras"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
            results = plugin.execute(
                Path("/project"),
                [mock_target_with_sources, mock_target_without_sources],
            )

        # Only the target with sources should produce a result
        assert len(results) == 1
        assert results[0].target is mock_target_with_sources
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd posit-bakery && python -m pytest test/plugins/builtin/oras/test_oras_plugin.py -v
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError` because `OrasPlugin` doesn't exist yet.

- [ ] **Step 3: Write OrasPlugin implementation**

Create `posit-bakery/posit_bakery/plugins/builtin/oras/__init__.py`:

```python
import logging
from pathlib import Path

import typer

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.oras.oras import OrasMergeWorkflow, find_oras_bin
from posit_bakery.plugins.protocol import BakeryToolPlugin, ToolCallResult

log = logging.getLogger(__name__)


class OrasPlugin(BakeryToolPlugin):
    name: str = "oras"
    description: str = "Merge multi-platform images using ORAS"

    def register_cli(self, app: typer.Typer) -> None:
        """Register the oras CLI commands with the given Typer app."""
        # CLI registration implemented in Task 3
        pass

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        platform: str | None = None,
        **kwargs,
    ) -> list[ToolCallResult]:
        """Execute ORAS merge workflow against the given image targets."""
        dry_run = kwargs.get("dry_run", False)
        results = []

        for target in targets:
            # Skip targets without merge sources
            if not target.get_merge_sources():
                log.debug(f"Skipping target '{target}' — no merge sources.")
                continue

            # Validate temp_registry
            if not target.settings.temp_registry:
                results.append(
                    ToolCallResult(
                        exit_code=1,
                        tool_name="oras",
                        target=target,
                        stdout="",
                        stderr=f"Cannot merge '{target}': temp_registry must be configured in settings.",
                    )
                )
                continue

            log.info(f"Merging sources for image UID '{target.uid}'")
            workflow = OrasMergeWorkflow.from_image_target(target)
            workflow_result = workflow.run(dry_run=dry_run)

            results.append(
                ToolCallResult(
                    exit_code=0 if workflow_result.success else 1,
                    tool_name="oras",
                    target=target,
                    stdout="",
                    stderr=workflow_result.error or "",
                    artifacts={"workflow_result": workflow_result},
                )
            )

        return results

    def display_results(self, results: list[ToolCallResult]) -> None:
        """Display ORAS merge results and exit non-zero on failures."""
        from posit_bakery.log import stderr_console

        has_errors = False
        for result in results:
            workflow_result = result.artifacts.get("workflow_result") if result.artifacts else None
            if result.exit_code != 0:
                has_errors = True
                stderr_console.print(
                    f"Error merging '{result.target}': {result.stderr}",
                    style="error",
                )
            elif workflow_result:
                log.info(
                    f"Merged '{result.target}' -> {', '.join(workflow_result.destinations)}"
                )

        if has_errors:
            stderr_console.print("\u274c ORAS merge(s) failed", style="error")
            raise typer.Exit(code=1)

        stderr_console.print("\u2705 ORAS merge completed", style="success")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd posit-bakery && python -m pytest test/plugins/builtin/oras/test_oras_plugin.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add posit-bakery/posit_bakery/plugins/builtin/oras/__init__.py posit-bakery/test/plugins/builtin/oras/
git commit -m "feat: add OrasPlugin with execute() and display_results()"
```

---

### Task 3: Add `bakery oras merge` CLI command

**Files:**
- Modify: `posit_bakery/plugins/builtin/oras/__init__.py` (the `register_cli` method)

- [ ] **Step 1: Write the test for CLI registration**

Add to `posit-bakery/test/plugins/builtin/oras/test_oras_plugin.py`:

```python
class TestOrasPluginCLI:
    def test_register_cli_adds_oras_command(self, plugin):
        app = typer.Typer()
        plugin.register_cli(app)

        # Verify the oras group was registered
        group_names = [g.name for g in app.registered_groups]
        assert "oras" in group_names
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd posit-bakery && python -m pytest test/plugins/builtin/oras/test_oras_plugin.py::TestOrasPluginCLI -v
```

Expected: FAIL because `register_cli` is a no-op (returns without adding commands).

- [ ] **Step 3: Implement `register_cli` with `merge` command**

Replace the `register_cli` method in `posit-bakery/posit_bakery/plugins/builtin/oras/__init__.py`:

```python
    def register_cli(self, app: typer.Typer) -> None:
        """Register the oras CLI commands with the given Typer app."""
        import glob as glob_module
        from typing import Annotated, Optional

        from posit_bakery.cli.common import with_verbosity_flags
        from posit_bakery.config.config import BakeryConfig, BakerySettings
        from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
        from posit_bakery.util import auto_path

        oras_app = typer.Typer(no_args_is_help=True)
        plugin = self

        @oras_app.command()
        @with_verbosity_flags
        def merge(
            metadata_file: Annotated[
                list[Path], typer.Argument(help="Path to input build metadata JSON file(s) to merge.")
            ],
            context: Annotated[
                Path,
                typer.Option(help="The root path to use. Defaults to the current working directory where invoked."),
            ] = auto_path(),
            temp_registry: Annotated[
                Optional[str],
                typer.Option(
                    help="Temporary registry to use for multiplatform split/merge builds.",
                    rich_help_panel="Build Configuration & Outputs",
                ),
            ] = None,
            dry_run: Annotated[
                bool, typer.Option(help="If set, the merged images will not be pushed to the registry.")
            ] = False,
        ):
            """Merge multi-platform images from build metadata files using ORAS.

            \b
            Takes one or more build metadata JSON files (produced by `bakery build --strategy build`)
            and merges platform-specific images into multi-platform manifest indexes.
            """
            settings = BakerySettings(
                dev_versions=DevVersionInclusionEnum.INCLUDE,
                matrix_versions=MatrixVersionInclusionEnum.INCLUDE,
                clean_temporary=False,
                temp_registry=temp_registry,
            )
            config: BakeryConfig = BakeryConfig.from_context(context, settings)

            # Resolve glob patterns in metadata_file arguments
            resolved_files: list[Path] = []
            for file in metadata_file:
                if "*" in str(file) or "?" in str(file) or "[" in str(file):
                    resolved_files.extend(sorted(Path(x).absolute() for x in glob_module.glob(str(file))))
                else:
                    resolved_files.append(file.absolute())
            metadata_file = resolved_files

            log.info(f"Reading targets from {', '.join(f.name for f in metadata_file)}")

            files_ok = True
            loaded_targets: list[str] = []
            for file in metadata_file:
                try:
                    loaded_targets.extend(config.load_build_metadata_from_file(file))
                except Exception as e:
                    log.error(f"Failed to load metadata from file '{file}'")
                    log.error(str(e))
                    files_ok = False
            loaded_targets = list(set(loaded_targets))

            if not files_ok:
                log.error("One or more metadata files are invalid, aborting merge.")
                raise typer.Exit(code=1)

            log.info(f"Found {len(loaded_targets)} targets")
            log.debug(", ".join(loaded_targets))

            results = plugin.execute(config.base_path, config.targets, dry_run=dry_run)
            plugin.display_results(results)

        app.add_typer(oras_app, name="oras", help="Merge multi-platform images using ORAS")
```

Add the missing `Path` import at the top of the file if not already present (it is — from `from pathlib import Path`). Add `import glob as glob_module` will be inside the method to avoid shadowing.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd posit-bakery && python -m pytest test/plugins/builtin/oras/test_oras_plugin.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add posit-bakery/posit_bakery/plugins/builtin/oras/__init__.py posit-bakery/test/plugins/builtin/oras/test_oras_plugin.py
git commit -m "feat: add bakery oras merge CLI command"
```

---

### Task 4: Register ORAS plugin entry point

**Files:**
- Modify: `posit_bakery/../../pyproject.toml:33-34`

- [ ] **Step 1: Add entry point for oras plugin**

In `posit-bakery/pyproject.toml`, find:

```toml
[project.entry-points."bakery.plugins"]
dgoss = "posit_bakery.plugins.builtin.dgoss:DGossPlugin"
```

Change to:

```toml
[project.entry-points."bakery.plugins"]
dgoss = "posit_bakery.plugins.builtin.dgoss:DGossPlugin"
oras = "posit_bakery.plugins.builtin.oras:OrasPlugin"
```

- [ ] **Step 2: Reinstall the package to register the entry point**

```bash
cd posit-bakery && pip install -e .
```

- [ ] **Step 3: Verify the plugin is discovered**

```bash
cd posit-bakery && python -c "from posit_bakery.plugins.registry import discover_plugins; plugins = discover_plugins(); print(list(plugins.keys()))"
```

Expected: output includes both `'dgoss'` and `'oras'`.

- [ ] **Step 4: Verify CLI registration**

```bash
cd posit-bakery && bakery oras --help
```

Expected: shows oras command group with `merge` subcommand.

- [ ] **Step 5: Commit**

```bash
git add posit-bakery/pyproject.toml
git commit -m "feat: register oras plugin entry point"
```

---

### Task 5: Refactor `bakery ci merge` to use OrasPlugin

**Files:**
- Modify: `posit_bakery/cli/ci.py:129-212`
- Modify: `posit_bakery/config/config.py:41` (remove import)
- Modify: `posit_bakery/config/config.py:985-1030` (remove `merge_targets`)

- [ ] **Step 1: Refactor `ci merge` command to delegate to oras plugin**

In `posit-bakery/posit_bakery/cli/ci.py`, replace the `merge` command (lines 129-213) with:

```python
@app.command()
@with_verbosity_flags
def merge(
    metadata_file: Annotated[list[Path], typer.Argument(help="Path to input build metadata JSON file(s) to merge.")],
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    temp_registry: Annotated[
        Optional[str],
        typer.Option(
            help="Temporary registry to use for multiplatform split/merge builds.",
            rich_help_panel="Build Configuration & Outputs",
        ),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option(help="If set, the merged images will not be pushed to the registry.")
    ] = False,
):
    """Merges multiple metadata files with single-platform images into a single multi-platform image by UID.
    This command is intended for use in CI workflows that utilize native builders for multiplatform builds.
    Easier multiplatform builds can be achieved by using emulation (Docker and QEMU), but builds in emulation typically
    suffer severe performance disadvantages.
    This command should be ran after multiple `bakery build --strategy build --platform <platform>
    --metadata-file <path> --temp-registry <registry>` commands have been executed for different platforms. The
    resulting metadata files can be fed into this command to merge and push combined multi-platform images. Matches are
    made by the top-level Image UID keys in the metadata files. Single entries with no other matches will be tagged and
    pushed as is. If an entry has no matching UID in the project, it will be skipped with a delayed error.
    Metadata files are expected to be JSON with the following structure:
    ```json
    {
      "<Image UID>": {metadata...}
    }
    ```
    """
    from posit_bakery.plugins.registry import get_plugin

    settings = BakerySettings(
        dev_versions=DevVersionInclusionEnum.INCLUDE,
        matrix_versions=MatrixVersionInclusionEnum.INCLUDE,
        clean_temporary=False,
        temp_registry=temp_registry,
    )
    config: BakeryConfig = BakeryConfig.from_context(context, settings)

    # Resolve glob patterns in metadata_file arguments
    resolved_files: list[Path] = []
    for file in metadata_file:
        if "*" in str(file) or "?" in str(file) or "[" in str(file):
            resolved_files.extend(sorted(Path(x).absolute() for x in glob.glob(str(file))))
        else:
            resolved_files.append(file.absolute())
    metadata_file = resolved_files

    log.info(f"Reading targets from {', '.join(f.name for f in metadata_file)}")

    files_ok = True
    loaded_targets: list[str] = []
    for file in metadata_file:
        try:
            loaded_targets.extend(config.load_build_metadata_from_file(file))
        except Exception as e:
            log.error(f"Failed to load metadata from file '{file}'")
            log.error(str(e))
            files_ok = False
    loaded_targets = list(set(loaded_targets))

    if not files_ok:
        log.error("One or more metadata files are invalid, aborting merge.")
        raise typer.Exit(code=1)

    log.info(f"Found {len(loaded_targets)} targets")
    log.debug(", ".join(loaded_targets))

    oras = get_plugin("oras")
    results = oras.execute(config.base_path, config.targets, dry_run=dry_run)

    # CI-specific: verify final manifests with imagetools inspect
    if not dry_run:
        import python_on_whales

        for result in results:
            if result.exit_code == 0 and result.artifacts:
                workflow_result = result.artifacts.get("workflow_result")
                if workflow_result and workflow_result.destinations:
                    manifest = python_on_whales.docker.buildx.imagetools.inspect(workflow_result.destinations[0])
                    stdout_console.print_json(manifest.model_dump_json(indent=2, exclude_unset=True, exclude_none=True))

    oras.display_results(results)
```

- [ ] **Step 2: Remove the `OrasMergeWorkflow` import from `config.py`**

In `posit-bakery/posit_bakery/config/config.py`, remove line 41:

```python
from posit_bakery.image.oras import OrasMergeWorkflow
```

- [ ] **Step 3: Remove `merge_targets()` from `config.py`**

In `posit-bakery/posit_bakery/config/config.py`, delete the `merge_targets` method (lines 985-1030). Also remove the `python_on_whales` import at line 1027 since it was only used inside that method (verify no other usage first — the import is inline so it's already gone with the method).

- [ ] **Step 4: Run the full test suite**

```bash
cd posit-bakery && python -m pytest test/ -v --ignore=test/image/oras -k "not slow"
```

Expected: all tests PASS. Any test referencing `config.merge_targets()` will need to be updated in the next step.

- [ ] **Step 5: Commit**

```bash
git add posit-bakery/posit_bakery/cli/ci.py posit-bakery/posit_bakery/config/config.py
git commit -m "refactor: bakery ci merge delegates to oras plugin"
```

---

### Task 6: Move and update ORAS tests

**Files:**
- Move: `test/image/oras/test_oras.py` -> `test/plugins/builtin/oras/test_oras.py`
- Delete: `test/image/oras/` (directory)

- [ ] **Step 1: Move the test file**

```bash
cp posit-bakery/test/image/oras/test_oras.py posit-bakery/test/plugins/builtin/oras/test_oras.py
rm -rf posit-bakery/test/image/oras/
```

- [ ] **Step 2: Update imports in the moved test file**

In `posit-bakery/test/plugins/builtin/oras/test_oras.py`, change:

```python
from posit_bakery.image.oras import (
    find_oras_bin,
    get_repository_from_ref,
    OrasCopy,
    OrasManifestDelete,
    OrasManifestIndexCreate,
    OrasMergeWorkflow,
    OrasMergeWorkflowResult,
)
```

to:

```python
from posit_bakery.plugins.builtin.oras.oras import (
    find_oras_bin,
    get_repository_from_ref,
    OrasCopy,
    OrasManifestDelete,
    OrasManifestIndexCreate,
    OrasMergeWorkflow,
    OrasMergeWorkflowResult,
)
```

- [ ] **Step 3: Update mock patch paths in the test file**

Find and replace all instances of `posit_bakery.image.oras.oras` in patch decorators/calls:

- `patch("posit_bakery.image.oras.oras.find_oras_bin"` -> `patch("posit_bakery.plugins.builtin.oras.oras.find_oras_bin"`

There are two occurrences: in `TestOrasMergeWorkflowFromImageTarget.test_from_image_target` (line 395) and `TestOrasMergeWorkflowIntegration.test_from_image_target_with_plain_http` (line 601).

- [ ] **Step 4: Run the moved tests**

```bash
cd posit-bakery && python -m pytest test/plugins/builtin/oras/ -v -k "not slow"
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add posit-bakery/test/image/oras posit-bakery/test/plugins/builtin/oras/
git commit -m "refactor: move oras tests to plugins/builtin/oras"
```

---

### Task 7: Full verification

**Files:** None (verification only)

- [ ] **Step 1: Run the complete test suite (excluding slow tests)**

```bash
cd posit-bakery && python -m pytest test/ -v -k "not slow"
```

Expected: all tests PASS.

- [ ] **Step 2: Verify no remaining references to old oras import paths**

```bash
cd posit-bakery && grep -r "posit_bakery.image.oras" --include="*.py" .
```

Expected: no matches.

- [ ] **Step 3: Verify no remaining references to `merge_targets`**

```bash
cd posit-bakery && grep -r "merge_targets" --include="*.py" .
```

Expected: no matches (or only in test mocks that have been updated).

- [ ] **Step 4: Verify CLI works end-to-end**

```bash
bakery oras --help
bakery oras merge --help
```

Expected: both show help text. The `merge` subcommand should list `metadata_file`, `--context`, `--temp-registry`, and `--dry-run` options.
