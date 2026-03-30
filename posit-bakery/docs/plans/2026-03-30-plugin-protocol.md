# Plugin Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor dgoss as a builtin plugin implementing the `BakeryToolPlugin` protocol, with plugin discovery via entry points and a deprecation bridge for `bakery run dgoss`.

**Architecture:** The plugin protocol defines a minimal contract (`register_cli` + `execute`). Plugins are discovered via Python entry points (`bakery.plugins` group). The dgoss plugin is a self-contained package at `posit_bakery/plugins/builtin/dgoss/` that owns its command model, execution suite, report models, and error type. The existing `bakery run dgoss` command becomes a thin deprecation wrapper.

**Tech Stack:** Python 3.10+, typer, pydantic, importlib.metadata (entry points)

**Spec:** `docs/specs/2026-03-30-plugin-protocol-design.md`

---

**All file paths are relative to the `posit-bakery/` directory** (the Python project root where `pyproject.toml` lives).

## File Structure

### New files

| File | Responsibility |
|---|---|
| `posit_bakery/plugins/protocol.py` | Already exists — update `BakeryToolPlugin` protocol and `ToolCallResult` |
| `posit_bakery/plugins/registry.py` | Plugin discovery via entry points and lookup by name |
| `posit_bakery/plugins/builtin/__init__.py` | Empty package marker |
| `posit_bakery/plugins/builtin/dgoss/__init__.py` | `DGossPlugin` class implementing `BakeryToolPlugin` |
| `posit_bakery/plugins/builtin/dgoss/command.py` | `DGossCommand` model + helper functions (moved from `image/goss/dgoss.py`) |
| `posit_bakery/plugins/builtin/dgoss/suite.py` | `DGossSuite` execution orchestration (moved from `image/goss/dgoss.py`) |
| `posit_bakery/plugins/builtin/dgoss/report.py` | Report models (moved from `image/goss/report.py`) |
| `posit_bakery/plugins/builtin/dgoss/errors.py` | `BakeryDGossError` (extracted from `error.py`) |
| `test/plugins/__init__.py` | Empty package marker |
| `test/plugins/test_registry.py` | Registry discovery and lookup tests |
| `test/plugins/builtin/__init__.py` | Empty package marker |
| `test/plugins/builtin/dgoss/__init__.py` | Empty package marker |
| `test/plugins/builtin/dgoss/test_command.py` | DGossCommand tests (moved from `test/image/goss/test_dgoss.py`) |
| `test/plugins/builtin/dgoss/test_suite.py` | DGossSuite tests (moved from `test/image/goss/test_dgoss.py`) |
| `test/plugins/builtin/dgoss/test_report.py` | Report tests (moved from `test/image/goss/test_report.py`) |
| `test/plugins/builtin/dgoss/testdata/basic_metadata.json` | Testdata (moved from `test/image/goss/testdata/`) |

### Modified files

| File | Change |
|---|---|
| `pyproject.toml` | Add `[project.entry-points."bakery.plugins"]` section |
| `posit_bakery/cli/main.py` | Call `discover_plugins()` and `register_cli()` at startup |
| `posit_bakery/cli/run.py` | Replace `dgoss` command body with deprecation wrapper |
| `posit_bakery/config/config.py` | Remove direct dgoss imports, use plugin registry |
| `posit_bakery/error.py` | Remove `BakeryDGossError` class (lines 156-188) |

### Removed files

| File | Reason |
|---|---|
| `posit_bakery/image/goss/__init__.py` | Module replaced by plugin |
| `posit_bakery/image/goss/dgoss.py` | Moved to `plugins/builtin/dgoss/command.py` and `suite.py` |
| `posit_bakery/image/goss/report.py` | Moved to `plugins/builtin/dgoss/report.py` |
| `test/image/goss/__init__.py` | Tests moved to `test/plugins/builtin/dgoss/` |
| `test/image/goss/test_dgoss.py` | Split into `test_command.py` and `test_suite.py` |
| `test/image/goss/test_report.py` | Moved to `test/plugins/builtin/dgoss/test_report.py` |
| `test/image/goss/testdata/` | Moved to `test/plugins/builtin/dgoss/testdata/` |

---

### Task 1: Update the plugin protocol

**Files:**
- Modify: `posit_bakery/plugins/protocol.py`
- Test: `test/plugins/test_registry.py` (protocol conformance test only)

- [ ] **Step 1: Write a protocol conformance test**

Create `test/plugins/__init__.py` and `test/plugins/test_registry.py`:

```python
# test/plugins/__init__.py
# (empty)
```

```python
# test/plugins/test_registry.py
import pytest
from posit_bakery.plugins.protocol import BakeryToolPlugin

pytestmark = [pytest.mark.unit]


class TestProtocol:
    def test_protocol_is_runtime_checkable(self):
        """BakeryToolPlugin must be runtime_checkable so we can validate plugins."""
        assert hasattr(BakeryToolPlugin, "__protocol_attrs__") or hasattr(
            BakeryToolPlugin, "__abstractmethods__"
        ), "BakeryToolPlugin should be a Protocol"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd posit-bakery && python -m pytest test/plugins/test_registry.py::TestProtocol::test_protocol_is_runtime_checkable -v`
Expected: FAIL — `BakeryToolPlugin` exists but is not `runtime_checkable`.

- [ ] **Step 3: Update the protocol**

Replace the contents of `posit_bakery/plugins/protocol.py` with:

```python
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import typer
from pydantic import BaseModel

from posit_bakery.image.image_target import ImageTarget


class ToolCallResult(BaseModel):
    """Represent the result of a tool call."""

    exit_code: int
    tool_name: str
    target: ImageTarget
    stdout: str
    stderr: str
    artifacts: dict[str, Any] | None = None


@runtime_checkable
class BakeryToolPlugin(Protocol):
    name: str
    description: str

    def register_cli(self, app: typer.Typer) -> None:
        """Register the plugin's CLI commands with the given Typer app."""
        ...

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        platform: str | None = None,
        **kwargs,
    ) -> list[ToolCallResult]:
        """Execute the plugin's tools against the given ImageTarget objects."""
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd posit-bakery && python -m pytest test/plugins/test_registry.py::TestProtocol::test_protocol_is_runtime_checkable -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add posit_bakery/plugins/protocol.py test/plugins/__init__.py test/plugins/test_registry.py
git commit -m "feat: update BakeryToolPlugin protocol with execute signature and runtime_checkable"
```

---

### Task 2: Create the plugin registry

**Files:**
- Create: `posit_bakery/plugins/registry.py`
- Test: `test/plugins/test_registry.py` (add registry tests)

- [ ] **Step 1: Write failing tests for the registry**

Append to `test/plugins/test_registry.py`:

```python
from unittest.mock import patch, MagicMock
from posit_bakery.plugins.registry import discover_plugins, get_plugin


class TestDiscoverPlugins:
    def test_discovers_dgoss_plugin(self):
        """discover_plugins should find the dgoss builtin plugin via entry points."""
        plugins = discover_plugins()
        assert "dgoss" in plugins

    def test_returns_dict_of_plugins(self):
        """discover_plugins should return a dict keyed by plugin name."""
        plugins = discover_plugins()
        assert isinstance(plugins, dict)
        for name, plugin in plugins.items():
            assert isinstance(name, str)
            assert hasattr(plugin, "name")
            assert hasattr(plugin, "execute")
            assert hasattr(plugin, "register_cli")


class TestGetPlugin:
    def test_get_existing_plugin(self):
        """get_plugin should return a plugin by name."""
        plugin = get_plugin("dgoss")
        assert plugin.name == "dgoss"

    def test_get_nonexistent_plugin_raises(self):
        """get_plugin should raise KeyError for unknown plugin names."""
        with pytest.raises(KeyError, match="no-such-plugin"):
            get_plugin("no-such-plugin")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd posit-bakery && python -m pytest test/plugins/test_registry.py::TestDiscoverPlugins -v test/plugins/test_registry.py::TestGetPlugin -v`
Expected: FAIL — `posit_bakery.plugins.registry` does not exist.

- [ ] **Step 3: Implement the registry**

Create `posit_bakery/plugins/registry.py`:

```python
import logging
from importlib.metadata import entry_points

from posit_bakery.plugins.protocol import BakeryToolPlugin

log = logging.getLogger(__name__)

_plugins: dict[str, BakeryToolPlugin] | None = None


def discover_plugins() -> dict[str, BakeryToolPlugin]:
    """Load all plugins from the bakery.plugins entry point group.

    Results are cached after the first call.
    """
    global _plugins
    if _plugins is not None:
        return _plugins

    _plugins = {}
    eps = entry_points(group="bakery.plugins")
    for ep in eps:
        try:
            plugin_cls = ep.load()
            plugin = plugin_cls()
            if not isinstance(plugin, BakeryToolPlugin):
                log.warning(
                    f"Plugin '{ep.name}' from '{ep.value}' does not satisfy BakeryToolPlugin protocol, skipping."
                )
                continue
            _plugins[plugin.name] = plugin
            log.debug(f"Loaded plugin '{plugin.name}' from '{ep.value}'")
        except Exception as e:
            log.warning(f"Failed to load plugin '{ep.name}' from '{ep.value}': {e}")

    return _plugins


def get_plugin(name: str) -> BakeryToolPlugin:
    """Get a specific plugin by name.

    :raises KeyError: If the plugin is not found.
    """
    plugins = discover_plugins()
    if name not in plugins:
        raise KeyError(f"Plugin '{name}' not found. Available plugins: {list(plugins.keys())}")
    return plugins[name]
```

- [ ] **Step 4: Run tests to verify they pass**

Note: The `TestDiscoverPlugins` and `TestGetPlugin` tests depend on the dgoss plugin being registered via entry points. These tests will fail until Task 3 (DGossPlugin) and Task 8 (pyproject.toml entry point) are complete. For now, verify the module imports and `TestGetPlugin.test_get_nonexistent_plugin_raises` passes:

Run: `cd posit-bakery && python -m pytest test/plugins/test_registry.py::TestGetPlugin::test_get_nonexistent_plugin_raises -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add posit_bakery/plugins/registry.py test/plugins/test_registry.py
git commit -m "feat: add plugin registry with entry point discovery"
```

---

### Task 3: Create the dgoss plugin error type

**Files:**
- Create: `posit_bakery/plugins/builtin/__init__.py`
- Create: `posit_bakery/plugins/builtin/dgoss/__init__.py` (empty initially)
- Create: `posit_bakery/plugins/builtin/dgoss/errors.py`

- [ ] **Step 1: Create package markers and the error module**

Create `posit_bakery/plugins/builtin/__init__.py`:

```python
# (empty)
```

Create `posit_bakery/plugins/builtin/dgoss/__init__.py`:

```python
# (empty — DGossPlugin will be added in Task 7)
```

Create `posit_bakery/plugins/builtin/dgoss/errors.py` — move `BakeryDGossError` from `posit_bakery/error.py`:

```python
import textwrap
from typing import List

from posit_bakery.error import BakeryToolRuntimeError


class BakeryDGossError(BakeryToolRuntimeError):
    def __init__(
        self,
        message: str = None,
        tool_name: str = None,
        cmd: List[str] = None,
        stdout: str | bytes | None = None,
        stderr: str | bytes | None = None,
        exit_code: int = 1,
        parse_error: Exception = None,
        metadata: dict | None = None,
    ) -> None:
        super().__init__(
            message=message,
            tool_name=tool_name,
            cmd=cmd,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            metadata=metadata,
        )
        self.parse_error = parse_error

    def __str__(self) -> str:
        s = f"{self.message}'\n"
        s += f"  - Exit code: {self.exit_code}\n"
        s += f"  - Command output: \n{textwrap.indent(self.dump_stdout(), '      ')}\n"
        s += f"  - Command executed: {' '.join(self.cmd)}\n"
        if self.metadata:
            s += "  - Metadata:\n"
            for key, value in self.metadata.items():
                s += f"    - {key}: {value}\n"
        return s
```

- [ ] **Step 2: Verify the module imports**

Run: `cd posit-bakery && python -c "from posit_bakery.plugins.builtin.dgoss.errors import BakeryDGossError; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add posit_bakery/plugins/builtin/__init__.py posit_bakery/plugins/builtin/dgoss/__init__.py posit_bakery/plugins/builtin/dgoss/errors.py
git commit -m "feat: add BakeryDGossError to dgoss plugin package"
```

---

### Task 4: Move report models to the dgoss plugin

**Files:**
- Create: `posit_bakery/plugins/builtin/dgoss/report.py`
- Create: `test/plugins/builtin/__init__.py`, `test/plugins/builtin/dgoss/__init__.py`
- Create: `test/plugins/builtin/dgoss/test_report.py`

- [ ] **Step 1: Copy report.py to the plugin**

Create `posit_bakery/plugins/builtin/dgoss/report.py` — this is an exact copy of `posit_bakery/image/goss/report.py` with no import changes needed (it only imports from `posit_bakery.image.image_target` which stays in place):

```python
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any
import sys

from pydantic import BaseModel, Field, computed_field
from rich.table import Table
from rich.text import Text

from posit_bakery.image.image_target import ImageTarget


class GossMatcherResult(BaseModel):
    """Models the matcher result of a Goss test case."""

    # Message should be set in all test results, even in skipped tests
    message: Annotated[str, Field(description="Matcher result summary string", default="")]

    # Expected and actual values are set in successful and failed tests, but not skipped tests
    expected: Annotated[
        list | dict | str | int | bool | None, Field(description="Expected value from goss.yaml", default=None)
    ]
    actual: Annotated[
        list | dict | str | int | bool | None, Field(description="Actual value from test result", default=None)
    ]

    # These fields are rarely set, mostly used for more complex matchers and transformations that we don't current use
    # in any of our image Goss tests. The types for these fields are highly variable and can be any JSON supported type
    # (string, number, boolean, array, object) depending on what's being tested. I used "Any" for now since I don't
    # expect type validation to be especially important here.
    extra_elements: Annotated[
        list[Any] | Any | None,
        Field(
            alias="extra-elements",
            description="Lists extra elements that appeared when using 'consist-of' matcher",
            default=None,
        ),
    ]
    found_elements: Annotated[
        list[Any] | Any | None,
        Field(
            alias="found-elements",
            description="Lists all found elements when using 'consist-of' or 'contain-element(s)' matchers",
            default=None,
        ),
    ]
    missing_elements: Annotated[
        list[Any] | Any | None,
        Field(
            alias="missing-elements",
            description=(
                "Lists all missing elements when using 'consist-of', 'have_patterns', or 'contain-element(s)' matchers"
            ),
            default=None,
        ),
    ]
    transform_chain: Annotated[
        Any | None,
        Field(
            alias="transform-chain",
            description=(
                "Lists any transformations applied to system state (actual) type in attempt to match expected type"
            ),
            default=None,
        ),
    ]
    untransformed_value: Annotated[
        Any | None,
        Field(
            alias="untransformed-value",
            description="Shows raw system state value if transformations were applied",
            default=None,
        ),
    ]


class GossResult(BaseModel):
    """Models the result of a single Goss test case."""

    successful: Annotated[bool, Field(description="Whether the test was successful")]
    skipped: Annotated[bool, Field(description="Whether the test was skipped")]
    err: Annotated[str | None, Field(description="Error message if Goss failed to execute the test", default=None)]
    result: Annotated[int, Field(description="Exit code from Goss test subprocess call")]

    resource_id: Annotated[str, Field(alias="resource-id", description="Test key in goss.yaml")]
    resource_type: Annotated[str, Field(alias="resource-type", description="Test type/section in goss.yaml")]
    property: Annotated[str, Field(alias="property", description="Element of test being checked")]
    title: Annotated[str, Field(description="Test title from goss.yaml (if present)", default="")]
    summary_line: Annotated[str, Field(alias="summary-line", description="Test summary string")]
    summary_line_compact: Annotated[
        str, Field(alias="summary-line-compact", description="One-liner test summary string")
    ]

    duration: Annotated[int, Field(description="Test duration in nanoseconds")]
    start_time: Annotated[
        datetime, Field(alias="start-time", description="Test start time in UTC, parsed from ISO 8601")
    ]
    end_time: Annotated[datetime, Field(alias="end-time", description="Test end time in UTC, parsed from ISO 8601")]

    matcher_result: Annotated[
        GossMatcherResult, Field(alias="matcher-result", description="Matcher result object, detailed test result data")
    ]
    meta: Annotated[dict[str, Any] | None, Field(description="Arbitrary metadata added by Goss", default=None)]


class GossSummary(BaseModel):
    """Models the summary section of a Goss JSON report."""

    test_count: Annotated[int, Field(alias="test-count", description="Total number of tests")]
    failed_count: Annotated[int, Field(alias="failed-count", description="Number of failed tests")]
    skipped_count: Annotated[int, Field(alias="skipped-count", description="Number of skipped tests")]
    summary_line: Annotated[str, Field(alias="summary-line", description="Summary string of test results")]
    total_duration: Annotated[int, Field(alias="total-duration", description="Total test duration in nanoseconds")]

    @computed_field(alias="success-count")
    @property
    def success_count(self) -> int:
        """Calculate the number of successful tests as it is not a defined field in Goss summaries."""
        return self.test_count - self.failed_count - self.skipped_count


class GossJsonReport(BaseModel):
    """Models Goss JSON reports produced by goss tests with `--format json`."""

    filepath: Annotated[Path | None, Field(default=None, exclude=True, description="Path to the report JSON file.")]
    summary: Annotated[GossSummary, Field(description="Summary of the test results.")]
    results: Annotated[list[GossResult] | None, Field(default=None, description="List of test results.")]

    @classmethod
    def load(cls, filepath: Path) -> "GossJsonReport":
        """Load a Goss JSON report from a file.

        :param filepath: Path to the Goss JSON report file.

        :return: An instance of GossJsonReport populated with data from the file.
        """
        with filepath.open("r") as file:
            data = cls.model_validate_json(file.read())
        return data

    @property
    def test_failures(self) -> list[GossResult]:
        """Returns a list of test results that failed (excluding skipped)."""
        if self.results is None:
            return []
        return [r for r in self.results if not r.successful and not r.skipped]

    @property
    def test_skips(self) -> list[GossResult]:
        """Returns a list of test results that were skipped."""
        if self.results is None:
            return []
        return [r for r in self.results if r.skipped]


class GossJsonReportCollection(dict):
    def add_report(self, image_target: ImageTarget, report: GossJsonReport):
        """Adds a GossJsonReport to the collection.

        :param image_target: The ImageTarget associated with the report.
        :param report: The GossJsonReport to add.
        """
        self.setdefault(image_target.image_name, dict())[image_target.uid] = (image_target, report)

    @property
    def test_failures(self) -> dict[str, list[GossResult]]:
        """Generates a dictionary of test failure lists by UID."""
        failures = {}
        for image_name, targets in self.items():
            for uid, (_, report) in targets.items():
                if not report.test_failures:
                    continue
                for failure in report.test_failures:
                    failures.setdefault(uid, list()).append(failure)
        return failures

    def aggregate(self) -> dict[str, dict]:
        """Aggregates the test results into a summary dictionary with the total of each test suite metric."""
        results = {"total": {"success": 0, "failed": 0, "skipped": 0, "total_tests": 0, "duration": 0}}
        for image_name, targets in self.items():
            for uid, (target, report) in targets.items():
                # If the image has no variant, show an empty string in the table
                if target.image_variant is None:
                    target.image_variant = type("ImageVariant", (), {"name": ""})
                # If the image has no OS, show an empty string in the table
                if target.image_os is None:
                    target.image_os = type("ImageVersionOS", (), {"name": ""})

                results.setdefault(image_name, dict())
                results[image_name].setdefault(target.image_version.name, dict())
                results[image_name][target.image_version.name].setdefault(target.image_os.name, dict())
                results[image_name][target.image_version.name][target.image_os.name].setdefault(
                    target.image_variant.name, dict()
                )
                results[image_name][target.image_version.name][target.image_os.name][target.image_variant.name] = {
                    "success": report.summary.success_count,
                    "failed": report.summary.failed_count,
                    "skipped": report.summary.skipped_count,
                    "total_tests": report.summary.test_count,
                    "duration": report.summary.total_duration,
                }
                results["total"]["success"] += report.summary.success_count
                results["total"]["failed"] += report.summary.failed_count
                results["total"]["skipped"] += report.summary.skipped_count
                results["total"]["total_tests"] += report.summary.test_count
                results["total"]["duration"] += report.summary.total_duration
        return results

    def table(self) -> Table:
        """Generates a rich table of the test results."""
        aggregated_results = self.aggregate()
        total_row = aggregated_results.pop("total")

        table = Table(title="Goss Test Results")
        table.add_column("Image Name", justify="left")
        table.add_column("Version", justify="left")
        table.add_column("OS", justify="left")
        table.add_column("Variant", justify="left")
        table.add_column("Success", justify="right", header_style="green3")
        table.add_column("Failed", justify="right", header_style="bright_red")
        table.add_column("Skipped", justify="right", header_style="yellow")
        table.add_column("Total Tests", justify="right")
        table.add_column("Duration", justify="right")

        for image_name, versions in aggregated_results.items():
            p_image_name = image_name
            for version, oses in versions.items():
                p_version = version
                for os_name, variants in oses.items():
                    p_os = os_name
                    for variant_name, result in variants.items():
                        success_style = "green3 bold" if result["failed"] == 0 else ""
                        failed_style = "bright_red bold" if result["failed"] > 0 else "bright_black italic"
                        skipped_style = "yellow bold" if result["skipped"] > 0 else "bright_black italic"
                        table.add_row(
                            p_image_name,
                            p_version,
                            p_os,
                            variant_name,
                            Text(str(result["success"]), style=success_style),
                            Text(str(result["failed"]), style=failed_style),
                            Text(str(result["skipped"]), style=skipped_style),
                            str(result["total_tests"]),
                            f"{result['duration'] / 1_000_000_000:.2f}s",
                        )
                        p_image_name = ""
                        p_version = ""
                        p_os = ""

        table.add_section()
        table.add_row(
            "Total",
            "",
            "",
            "",
            str(total_row["success"]),
            str(total_row["failed"]),
            str(total_row["skipped"]),
            str(total_row["total_tests"]),
            f"{total_row['duration'] / 1_000_000_000:.2f}s",
        )

        return table
```

- [ ] **Step 2: Create test package markers and move report tests**

Create `test/plugins/builtin/__init__.py`:

```python
# (empty)
```

Create `test/plugins/builtin/dgoss/__init__.py`:

```python
# (empty)
```

Create `test/plugins/builtin/dgoss/test_report.py` — this is the contents of `test/image/goss/test_report.py` with the import updated:

```python
"""Tests for posit_bakery.plugins.builtin.dgoss.report module.

Tests cover the Goss report parsing and aggregation functionality.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from posit_bakery.plugins.builtin.dgoss.report import (
    GossMatcherResult,
    GossResult,
    GossSummary,
    GossJsonReport,
    GossJsonReportCollection,
)
from posit_bakery.image.image_target import ImageTarget


pytestmark = [pytest.mark.unit, pytest.mark.goss]
```

Copy the rest of the file (all fixtures and test classes) verbatim from `test/image/goss/test_report.py` — starting from line 22 (`pytestmark = ...`) through the end. The only change is the import block above.

- [ ] **Step 3: Run report tests from the new location**

Run: `cd posit-bakery && python -m pytest test/plugins/builtin/dgoss/test_report.py -v`
Expected: All tests PASS (same tests, new import path).

- [ ] **Step 4: Commit**

```bash
git add posit_bakery/plugins/builtin/dgoss/report.py test/plugins/builtin/__init__.py test/plugins/builtin/dgoss/__init__.py test/plugins/builtin/dgoss/test_report.py
git commit -m "feat: move goss report models to dgoss plugin"
```

---

### Task 5: Move DGossCommand to the dgoss plugin

**Files:**
- Create: `posit_bakery/plugins/builtin/dgoss/command.py`
- Create: `test/plugins/builtin/dgoss/test_command.py`
- Create: `test/plugins/builtin/dgoss/testdata/basic_metadata.json`

- [ ] **Step 1: Copy testdata**

Copy `test/image/goss/testdata/basic_metadata.json` to `test/plugins/builtin/dgoss/testdata/basic_metadata.json`.

- [ ] **Step 2: Create command.py**

Create `posit_bakery/plugins/builtin/dgoss/command.py` — the `DGossCommand` class and helper functions moved from `posit_bakery/image/goss/dgoss.py`, with updated imports:

```python
import re
from pathlib import Path
from typing import Annotated, Self, Literal

from pydantic import BaseModel, Field, model_validator, computed_field

from posit_bakery.image.image_target import ImageTargetContext, ImageTarget
from posit_bakery.util import find_bin


def find_dgoss_bin(context: ImageTargetContext) -> str | None:
    """Find the path to the DGoss binary for the given image target's context.

    :param context: The context of the image target to search for the DGoss binary.
    """
    return find_bin(context.base_path, "dgoss", "DGOSS_PATH") or "dgoss"


def find_goss_bin(context: ImageTargetContext) -> str | None:
    """Find the path to the Goss binary for the given image target's context.

    :param context: The context of the image target to search for the Goss binary.
    """
    return find_bin(context.base_path, "goss", "GOSS_PATH")


def find_test_path(context: ImageTargetContext) -> Path | None:
    """Find the path to the Goss test directory for the given image target's context."""
    # Check for tests in the version path first
    tests_path = context.version_path / "test"
    if tests_path.exists():
        return tests_path

    # If not found, check in the image path
    tests_path = context.image_path / "test"
    if tests_path.exists():
        return tests_path

    # If not found, return None to indicate no tests found
    return None


class DGossCommand(BaseModel):
    image_target: ImageTarget
    dgoss_bin: Annotated[str, Field(default_factory=lambda data: find_dgoss_bin(data["image_target"].context))]
    goss_bin: Annotated[str | None, Field(default_factory=lambda data: find_goss_bin(data["image_target"].context))]
    dgoss_command: Annotated[str, Field(default="run")]
    version_mountpoint: Literal["/tmp/version"] = "/tmp/version"
    image_mountpoint: Literal["/tmp/image"] = "/tmp/image"
    project_mountpoint: Literal["/tmp/project"] = "/tmp/project"

    platform: Annotated[str | None, Field(default=None, description="The platform to target for container execution.")]
    test_path: Annotated[Path | None, Field(default_factory=lambda data: find_test_path(data["image_target"].context))]
    runtime_options: Annotated[str | None, Field(default=None, description="Additional runtime options for dgoss.")]
    wait: Annotated[int, Field(default=0)]
    image_command: Annotated[str, Field(default="sleep infinity")]

    @property
    def dgoss_environment(self) -> dict[str, str]:
        """Return the environment variables for the DGoss command."""
        env = {
            "GOSS_FILES_PATH": str(self.test_path),
            "GOSS_OPTS": "--format json --no-color",
        }
        if self.goss_bin:
            env["GOSS_PATH"] = self.goss_bin
        if self.wait > 0:
            env["GOSS_SLEEP"] = str(self.wait)
        return env

    @property
    def image_environment(self) -> dict[str, str]:
        """Return the environment variables for the DGoss command."""
        e = {
            "IMAGE_VERSION": self.image_target.image_version.name,
            "IMAGE_VERSION_MOUNT": str(self.version_mountpoint),
            "IMAGE_MOUNT": str(self.image_mountpoint),
            "PROJECT_MOUNT": str(self.project_mountpoint),
        }
        if self.image_target.image_variant:
            e["IMAGE_VARIANT"] = self.image_target.image_variant.name
        if self.image_target.image_os:
            e["IMAGE_OS"] = self.image_target.image_os.name
            e["IMAGE_OS_NAME"] = self.image_target.image_os.buildOS.name
            e["IMAGE_OS_CODENAME"] = self.image_target.image_os.buildOS.codename or ""
            e["IMAGE_OS_FAMILY"] = self.image_target.image_os.buildOS.family.value
            e["IMAGE_OS_VERSION"] = self.image_target.image_os.buildOS.version
        if self.image_target.build_args:
            for arg, value in self.image_target.build_args.items():
                env_var = f"BUILD_ARG_{arg.upper()}"
                e[env_var] = value

        return e

    @property
    def volume_mounts(self) -> list[tuple[str, str]]:
        return [
            (str(self.image_target.context.version_path.resolve()), str(self.version_mountpoint)),
            (str(self.image_target.context.image_path.resolve()), str(self.image_mountpoint)),
            (str(self.image_target.context.base_path.resolve()), str(self.project_mountpoint)),
        ]

    @classmethod
    def from_image_target(cls, image_target: ImageTarget, platform: str | None = None) -> "DGossCommand":
        args = {
            "image_target": image_target,
        }
        if platform:
            args["platform"] = platform
        if image_target.image_variant:
            goss_options = image_target.image_variant.get_tool_option("goss")
            if goss_options is not None:
                args["runtime_options"] = goss_options.runtimeOptions
                args["image_command"] = goss_options.command
                args["wait"] = goss_options.wait
        return cls(**args)

    @model_validator(mode="after")
    def validate(self) -> Self:
        """Validate the DGoss command configuration."""
        if not self.dgoss_bin:
            raise ValueError(
                "dgoss binary path must be specified with the `DGOSS_PATH` environment variable if it cannot be "
                "discovered in the system PATH."
            )
        if not self.test_path:
            raise ValueError(
                f"No test directory was found for target '{str(self.image_target)}'. Ensure the test directory "
                f"and test/goss.yaml file exist in either the version path or image path."
            )
        return self

    @computed_field
    @property
    def command(self) -> list[str]:
        """Return the full DGoss command to run."""
        cmd = [self.dgoss_bin, self.dgoss_command]

        if self.platform:
            cmd.extend(["--platform", self.platform])
        for mount in self.volume_mounts:
            cmd.extend(["-v", f"{mount[0]}:{mount[1]}"])
        for env_var, value in self.image_environment.items():
            if value is not None:
                env_value = re.sub(r"([\"\'\\$`!*?&#()|<>;\[\]{}\s])", r"\\\1", value)
                cmd.extend(["-e", f"{env_var}={env_value}"])
        cmd.append("--init")
        if self.runtime_options:
            # TODO: We may want to validate this to ensure options are not duplicated.
            cmd.extend(self.runtime_options.split())
        if self.platform:
            cmd.append(self.image_target.ref(self.platform))
        else:
            cmd.append(self.image_target.ref())
        cmd.extend(self.image_command.split())

        return cmd
```

- [ ] **Step 3: Create test_command.py**

Create `test/plugins/builtin/dgoss/test_command.py` — the `TestDGossCommand` tests from `test/image/goss/test_dgoss.py` with updated imports:

```python
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from posit_bakery.config.dependencies import PythonDependencyVersions, RDependencyVersions
from posit_bakery.plugins.builtin.dgoss.command import DGossCommand, find_dgoss_bin
from posit_bakery.image.image_metadata import MetadataFile

pytestmark = [
    pytest.mark.unit,
    pytest.mark.goss,
]

DGOSS_TESTDATA_DIR = (Path(__file__).parent / "testdata").absolute()


class TestDGossCommand:
    def test_from_image_target(self, basic_standard_image_target):
        """Test that DGossCommand initializes with the correct attributes."""
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target)
        assert dgoss_command.image_target == basic_standard_image_target
        assert basic_standard_image_target.context.version_path / "test" == dgoss_command.test_path
        assert dgoss_command.wait == 1

    def test_dgoss_environment(self, basic_standard_image_target):
        """Test that DGossCommand dgoss_environment returns the expected environment variables."""
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target)
        expected_env = {
            "GOSS_FILES_PATH": str(basic_standard_image_target.context.version_path / "test"),
            "GOSS_SLEEP": "1",
            "GOSS_OPTS": "--format json --no-color",
        }
        for key, value in expected_env.items():
            assert dgoss_command.dgoss_environment[key] == value, (
                f"Expected {key} to be {value}, got {dgoss_command.dgoss_environment[key]}"
            )

    def test_image_environment(self, basic_standard_image_target):
        """Test that DGossCommand image_environment returns the expected environment variables."""
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target)
        expected_env = {
            "IMAGE_VERSION": basic_standard_image_target.image_version.name,
            "IMAGE_VERSION_MOUNT": "/tmp/version",
            "IMAGE_MOUNT": "/tmp/image",
            "PROJECT_MOUNT": "/tmp/project",
            "IMAGE_VARIANT": basic_standard_image_target.image_variant.name,
            "IMAGE_OS": basic_standard_image_target.image_os.name,
            "IMAGE_OS_NAME": basic_standard_image_target.image_os.buildOS.name,
            "IMAGE_OS_VERSION": basic_standard_image_target.image_os.buildOS.version,
            "IMAGE_OS_FAMILY": basic_standard_image_target.image_os.buildOS.family,
            "IMAGE_OS_CODENAME": basic_standard_image_target.image_os.buildOS.codename,
        }
        assert dgoss_command.image_environment == expected_env

    def test_volume_mounts(self, basic_standard_image_target):
        """Test that DGossCommand volume_mounts returns the expected volume mounts."""
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target)
        expected_mounts = [
            (str(basic_standard_image_target.context.version_path.resolve()), "/tmp/version"),
            (str(basic_standard_image_target.context.image_path.resolve()), "/tmp/image"),
            (str(basic_standard_image_target.context.base_path.resolve()), "/tmp/project"),
        ]
        assert dgoss_command.volume_mounts == expected_mounts

    def test_validate_no_dgoss(self, basic_standard_image_target):
        """Test that DGossCommand validate checks the test path."""
        with patch("posit_bakery.plugins.builtin.dgoss.command.find_dgoss_bin") as mock_find_dgoss_bin:
            mock_find_dgoss_bin.return_value = None
            with pytest.raises(ValidationError, match="dgoss binary path must be specified"):
                DGossCommand.from_image_target(image_target=basic_standard_image_target)

    def test_validate_no_test_path(self, get_tmpconfig):
        """Test that DGossCommand validate raises an error if the test path does not exist."""
        basic_tmpconfig = get_tmpconfig("basic")
        shutil.rmtree(basic_tmpconfig.targets[0].context.version_path / "test")
        with pytest.raises(ValidationError, match="No test directory was found"):
            DGossCommand.from_image_target(image_target=basic_tmpconfig.targets[0])

    def test_command(self, basic_standard_image_target):
        """Test that DGossCommand command returns the expected command."""
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target)
        expected_command = [
            find_dgoss_bin(basic_standard_image_target.context),
            "run",
            "-v",
            f"{str(basic_standard_image_target.context.version_path.resolve())}:/tmp/version",
            "-v",
            f"{str(basic_standard_image_target.context.image_path.resolve())}:/tmp/image",
            "-v",
            f"{str(basic_standard_image_target.context.base_path.resolve())}:/tmp/project",
            "-e",
            "IMAGE_VERSION=1.0.0",
            "-e",
            "IMAGE_VERSION_MOUNT=/tmp/version",
            "-e",
            "IMAGE_MOUNT=/tmp/image",
            "-e",
            "PROJECT_MOUNT=/tmp/project",
            "-e",
            "IMAGE_VARIANT=Standard",
            "-e",
            "IMAGE_OS=Ubuntu\\ 22.04",
            "-e",
            "IMAGE_OS_NAME=ubuntu",
            "-e",
            "IMAGE_OS_CODENAME=jammy",
            "-e",
            "IMAGE_OS_FAMILY=debian",
            "-e",
            "IMAGE_OS_VERSION=22.04",
            "--init",
            basic_standard_image_target.ref(),
            *basic_standard_image_target.image_variant.get_tool_option("goss").command.split(),
        ]
        assert dgoss_command.command == expected_command

    def test_command_build_args_env_vars(self, basic_standard_image_target):
        """Test that DGossCommand command returns the expected command."""
        basic_standard_image_target.image_version.isMatrixVersion = True
        basic_standard_image_target.image_version.dependencies = [
            PythonDependencyVersions(dependency="python", versions=["3.13.7"]),
            RDependencyVersions(dependency="R", versions=["4.3.3"]),
        ]
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target)
        expected_command = [
            find_dgoss_bin(basic_standard_image_target.context),
            "run",
            "-v",
            f"{str(basic_standard_image_target.context.version_path.resolve())}:/tmp/version",
            "-v",
            f"{str(basic_standard_image_target.context.image_path.resolve())}:/tmp/image",
            "-v",
            f"{str(basic_standard_image_target.context.base_path.resolve())}:/tmp/project",
            "-e",
            "IMAGE_VERSION=1.0.0",
            "-e",
            "IMAGE_VERSION_MOUNT=/tmp/version",
            "-e",
            "IMAGE_MOUNT=/tmp/image",
            "-e",
            "PROJECT_MOUNT=/tmp/project",
            "-e",
            "IMAGE_VARIANT=Standard",
            "-e",
            "IMAGE_OS=Ubuntu\\ 22.04",
            "-e",
            "IMAGE_OS_NAME=ubuntu",
            "-e",
            "IMAGE_OS_CODENAME=jammy",
            "-e",
            "IMAGE_OS_FAMILY=debian",
            "-e",
            "IMAGE_OS_VERSION=22.04",
            "-e",
            "BUILD_ARG_PYTHON_VERSION=3.13.7",
            "-e",
            "BUILD_ARG_R_VERSION=4.3.3",
            "--init",
            basic_standard_image_target.ref(),
            *basic_standard_image_target.image_variant.get_tool_option("goss").command.split(),
        ]
        assert dgoss_command.command == expected_command

    def test_command_with_platform_option(self, basic_standard_image_target):
        """Test that DGossCommand command returns the expected command."""
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target, platform="linux/arm64")
        expected_command = [
            find_dgoss_bin(basic_standard_image_target.context),
            "run",
            "--platform",
            "linux/arm64",
            "-v",
            f"{str(basic_standard_image_target.context.version_path.resolve())}:/tmp/version",
            "-v",
            f"{str(basic_standard_image_target.context.image_path.resolve())}:/tmp/image",
            "-v",
            f"{str(basic_standard_image_target.context.base_path.resolve())}:/tmp/project",
            "-e",
            "IMAGE_VERSION=1.0.0",
            "-e",
            "IMAGE_VERSION_MOUNT=/tmp/version",
            "-e",
            "IMAGE_MOUNT=/tmp/image",
            "-e",
            "PROJECT_MOUNT=/tmp/project",
            "-e",
            "IMAGE_VARIANT=Standard",
            "-e",
            "IMAGE_OS=Ubuntu\\ 22.04",
            "-e",
            "IMAGE_OS_NAME=ubuntu",
            "-e",
            "IMAGE_OS_CODENAME=jammy",
            "-e",
            "IMAGE_OS_FAMILY=debian",
            "-e",
            "IMAGE_OS_VERSION=22.04",
            "--init",
            basic_standard_image_target.ref("linux/arm64"),
            *basic_standard_image_target.image_variant.get_tool_option("goss").command.split(),
        ]
        assert dgoss_command.command == expected_command

    def test_command_with_runtime_options(self, basic_standard_image_target):
        """Test that DGossCommand command returns the expected command."""
        basic_standard_image_target.image_variant.options[0].runtimeOptions = "--privileged"
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target)
        expected_command = [
            find_dgoss_bin(basic_standard_image_target.context),
            "run",
            "-v",
            f"{str(basic_standard_image_target.context.version_path.resolve())}:/tmp/version",
            "-v",
            f"{str(basic_standard_image_target.context.image_path.resolve())}:/tmp/image",
            "-v",
            f"{str(basic_standard_image_target.context.base_path.resolve())}:/tmp/project",
            "-e",
            "IMAGE_VERSION=1.0.0",
            "-e",
            "IMAGE_VERSION_MOUNT=/tmp/version",
            "-e",
            "IMAGE_MOUNT=/tmp/image",
            "-e",
            "PROJECT_MOUNT=/tmp/project",
            "-e",
            "IMAGE_VARIANT=Standard",
            "-e",
            "IMAGE_OS=Ubuntu\\ 22.04",
            "-e",
            "IMAGE_OS_NAME=ubuntu",
            "-e",
            "IMAGE_OS_CODENAME=jammy",
            "-e",
            "IMAGE_OS_FAMILY=debian",
            "-e",
            "IMAGE_OS_VERSION=22.04",
            "--init",
            "--privileged",
            basic_standard_image_target.ref(),
            *basic_standard_image_target.image_variant.get_tool_option("goss").command.split(),
        ]
        assert dgoss_command.command == expected_command

    def test_command_with_build_metadata(self, basic_standard_image_target):
        """Test that DGossCommand command returns the expected command."""
        basic_standard_image_target.load_build_metadata_from_file(
            MetadataFile.load(DGOSS_TESTDATA_DIR / "basic_metadata.json")
        )
        assert (
            basic_standard_image_target.ref()
            == "docker.io/posit/test-image:1.0.0@sha256:80a50319320bf34740251482b7c06bf6dddb52aa82ea4cbffa812ed2fafaa0b9"
        )
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target)
        expected_command = [
            find_dgoss_bin(basic_standard_image_target.context),
            "run",
            "-v",
            f"{str(basic_standard_image_target.context.version_path.resolve())}:/tmp/version",
            "-v",
            f"{str(basic_standard_image_target.context.image_path.resolve())}:/tmp/image",
            "-v",
            f"{str(basic_standard_image_target.context.base_path.resolve())}:/tmp/project",
            "-e",
            "IMAGE_VERSION=1.0.0",
            "-e",
            "IMAGE_VERSION_MOUNT=/tmp/version",
            "-e",
            "IMAGE_MOUNT=/tmp/image",
            "-e",
            "PROJECT_MOUNT=/tmp/project",
            "-e",
            "IMAGE_VARIANT=Standard",
            "-e",
            "IMAGE_OS=Ubuntu\\ 22.04",
            "-e",
            "IMAGE_OS_NAME=ubuntu",
            "-e",
            "IMAGE_OS_CODENAME=jammy",
            "-e",
            "IMAGE_OS_FAMILY=debian",
            "-e",
            "IMAGE_OS_VERSION=22.04",
            "--init",
            basic_standard_image_target.ref(),
            *basic_standard_image_target.image_variant.get_tool_option("goss").command.split(),
        ]
        assert dgoss_command.command == expected_command
```

- [ ] **Step 4: Run command tests from the new location**

Run: `cd posit-bakery && python -m pytest test/plugins/builtin/dgoss/test_command.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add posit_bakery/plugins/builtin/dgoss/command.py test/plugins/builtin/dgoss/test_command.py test/plugins/builtin/dgoss/testdata/
git commit -m "feat: move DGossCommand to dgoss plugin"
```

---

### Task 6: Move DGossSuite to the dgoss plugin

**Files:**
- Create: `posit_bakery/plugins/builtin/dgoss/suite.py`
- Create: `test/plugins/builtin/dgoss/test_suite.py`

- [ ] **Step 1: Create suite.py**

Create `posit_bakery/plugins/builtin/dgoss/suite.py` — moved from `posit_bakery/image/goss/dgoss.py` (the `DGossSuite` class) with updated imports:

```python
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path

import pydantic

from posit_bakery.error import BakeryToolRuntimeError, BakeryToolRuntimeErrorGroup
from posit_bakery.plugins.builtin.dgoss.command import DGossCommand
from posit_bakery.plugins.builtin.dgoss.errors import BakeryDGossError
from posit_bakery.plugins.builtin.dgoss.report import GossJsonReportCollection, GossJsonReport
from posit_bakery.image.image_target import ImageTarget

log = logging.getLogger(__name__)


class DGossSuite:
    def __init__(self, context: Path, image_targets: list[ImageTarget], platform: str | None = None) -> None:
        self.context = context
        self.image_targets = image_targets
        self.dgoss_commands = [DGossCommand.from_image_target(target, platform=platform) for target in image_targets]

    def run(self) -> tuple[GossJsonReportCollection, BakeryToolRuntimeError | BakeryToolRuntimeErrorGroup | None]:
        results_dir = self.context / "results" / "dgoss"
        if results_dir.exists():
            shutil.rmtree(results_dir)
        results_dir.mkdir(parents=True)

        report_collection = GossJsonReportCollection()
        errors = []

        for dgoss_command in self.dgoss_commands:
            log.info(f"[bright_blue bold]=== Running Goss tests for '{str(dgoss_command.image_target)}' ===")
            log.debug(f"[bright_black]Environment variables: {dgoss_command.dgoss_environment}")
            log.debug(f"[bright_black]Executing dgoss command: {' '.join(dgoss_command.command)}")

            run_env = os.environ.copy()
            run_env.update(dgoss_command.dgoss_environment)
            p = subprocess.run(dgoss_command.command, env=run_env, cwd=self.context, capture_output=True)
            exit_code = p.returncode

            image_subdir = results_dir / dgoss_command.image_target.image_name
            image_subdir.mkdir(parents=True, exist_ok=True)
            results_file = image_subdir / f"{dgoss_command.image_target.uid}.json"

            try:
                output = p.stdout.decode("utf-8")
                output = output.strip()
            except UnicodeDecodeError:
                log.warning(f"Unexpected encoding for dgoss output for image '{str(dgoss_command.image_target)}'.")
                output = p.stdout
            parse_err = None

            try:
                result_data = json.loads(output)
                output = json.dumps(result_data, indent=2)
                report_collection.add_report(
                    dgoss_command.image_target, GossJsonReport(filepath=results_file, **result_data)
                )
            except json.JSONDecodeError as e:
                log.error(f"Failed to decode JSON output from dgoss for image '{str(dgoss_command.image_target)}': {e}")
                parse_err = e
            except pydantic.ValidationError as e:
                log.error(
                    f"Failed to load result data for summary from dgoss for image '{str(dgoss_command.image_target)}: {e}"
                )
                log.warning(f"Test results will be excluded from '{str(dgoss_command.image_target)}' in final summary.")
                parse_err = e

            if not parse_err:
                with open(results_file, "w") as f:
                    log.info(f"Writing results to {results_file}")
                    f.write(output)

            # Goss can exit 1 in multiple scenarios including test failures and incorrect configurations. From Bakery's
            # perspective, we only want to report an error back if the execution of Goss failed in some way. Our best
            # method of doing this is to check if both the exit code is non-zero, and we were unable to parse the output
            # of the command.
            if exit_code != 0 and parse_err is not None:
                log.error(f"dgoss for image '{str(dgoss_command.image_target)}' exited with code {exit_code}")
                errors.append(
                    BakeryDGossError(
                        f"dgoss execution failed for image '{str(dgoss_command.image_target)}'",
                        "dgoss",
                        cmd=dgoss_command.command,
                        stdout=p.stdout,
                        stderr=p.stderr,
                        parse_error=parse_err,
                        exit_code=exit_code,
                        metadata={"environment_variables": dgoss_command.dgoss_environment},
                    )
                )
            elif exit_code == 0:
                log.info(f"[bright_green bold]Goss tests passed for '{str(dgoss_command.image_target)}'")
            else:
                log.warning(f"[yellow bold]Goss tests failed for '{str(dgoss_command.image_target)}'")

        if errors:
            if len(errors) == 1:
                errors = errors[0]
            else:
                errors = BakeryToolRuntimeErrorGroup(f"dgoss runtime errors occurred for multiple images.", errors)
        else:
            errors = None
        return report_collection, errors
```

- [ ] **Step 2: Create test_suite.py**

Create `test/plugins/builtin/dgoss/test_suite.py`:

```python
import json

import pytest

from posit_bakery.plugins.builtin.dgoss.suite import DGossSuite
from test.helpers import remove_images

pytestmark = [
    pytest.mark.unit,
    pytest.mark.goss,
]


class TestDGossSuite:
    def test_init(self, get_config_obj):
        """Test that DGossSuite initializes with the correct attributes."""
        basic_config_obj = get_config_obj("basic")
        dgoss_suite = DGossSuite(basic_config_obj.base_path, basic_config_obj.targets)
        assert dgoss_suite.context == basic_config_obj.base_path
        assert dgoss_suite.image_targets == basic_config_obj.targets
        assert len(dgoss_suite.dgoss_commands) == 2

    @pytest.mark.slow
    @pytest.mark.xdist_group(name="build")
    def test_run(self, get_tmpconfig):
        """Test that DGossSuite run executes the DGoss commands."""
        basic_tmpconfig = get_tmpconfig("basic")
        basic_tmpconfig.build_targets()

        dgoss_suite = DGossSuite(basic_tmpconfig.base_path, basic_tmpconfig.targets)

        report_collection, errors = dgoss_suite.run()

        assert errors is None
        assert len(report_collection.test_failures) == 0
        assert len(report_collection.get("test-image")) == 2
        for target in dgoss_suite.image_targets:
            results_file = target.context.base_path / "results" / "dgoss" / target.image_name / f"{target.uid}.json"
            assert results_file.exists()
            with open(results_file) as f:
                json.load(f)

        remove_images(basic_tmpconfig)
```

- [ ] **Step 3: Run suite tests from the new location**

Run: `cd posit-bakery && python -m pytest test/plugins/builtin/dgoss/test_suite.py::TestDGossSuite::test_init -v`
Expected: PASS (the slow `test_run` test requires Docker, so just verify `test_init`).

- [ ] **Step 4: Commit**

```bash
git add posit_bakery/plugins/builtin/dgoss/suite.py test/plugins/builtin/dgoss/test_suite.py
git commit -m "feat: move DGossSuite to dgoss plugin"
```

---

### Task 7: Implement DGossPlugin class

**Files:**
- Modify: `posit_bakery/plugins/builtin/dgoss/__init__.py`
- Test: `test/plugins/test_registry.py` (add conformance test)

- [ ] **Step 1: Write a protocol conformance test**

Add to `test/plugins/test_registry.py`:

```python
from posit_bakery.plugins.builtin.dgoss import DGossPlugin


class TestDGossPlugin:
    def test_satisfies_protocol(self):
        """DGossPlugin must satisfy BakeryToolPlugin protocol."""
        plugin = DGossPlugin()
        assert isinstance(plugin, BakeryToolPlugin)

    def test_has_required_attributes(self):
        """DGossPlugin must have name and description."""
        plugin = DGossPlugin()
        assert plugin.name == "dgoss"
        assert isinstance(plugin.description, str)
        assert len(plugin.description) > 0

    def test_register_cli_creates_command_group(self):
        """register_cli should add a 'dgoss' command group to the app."""
        import typer
        app = typer.Typer()
        plugin = DGossPlugin()
        plugin.register_cli(app)
        # Verify a command group was registered — typer stores registered groups internally
        group_names = [info.name for info in app.registered_groups]
        assert "dgoss" in group_names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd posit-bakery && python -m pytest test/plugins/test_registry.py::TestDGossPlugin -v`
Expected: FAIL — `DGossPlugin` does not exist yet.

- [ ] **Step 3: Implement DGossPlugin**

Replace `posit_bakery/plugins/builtin/dgoss/__init__.py` with:

```python
import logging
import re
import warnings
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.config.config import BakeryConfig, BakeryConfigFilter, BakerySettings
from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.log import stderr_console
from posit_bakery.plugins.builtin.dgoss.report import GossJsonReportCollection
from posit_bakery.plugins.builtin.dgoss.suite import DGossSuite
from posit_bakery.error import BakeryToolRuntimeErrorGroup
from posit_bakery.plugins.protocol import ToolCallResult
from posit_bakery.settings import SETTINGS
from posit_bakery.util import auto_path

log = logging.getLogger(__name__)


class RichHelpPanelEnum(str, Enum):
    """Enum for categorizing options into rich help panels."""

    FILTERS = "Filters"


class DGossPlugin:
    name: str = "dgoss"
    description: str = "Run Goss tests against container images"

    def register_cli(self, app: typer.Typer) -> None:
        """Register the dgoss command group with the root Typer app."""
        dgoss_app = typer.Typer(no_args_is_help=True)

        @dgoss_app.command(name="run")
        def dgoss_run(
            context: Annotated[
                Path,
                typer.Option(
                    exists=True,
                    file_okay=False,
                    dir_okay=True,
                    readable=True,
                    writable=True,
                    resolve_path=True,
                    help="The root path to use. Defaults to the current working directory where invoked.",
                ),
            ] = auto_path(),
            image_name: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image name to isolate goss testing to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_version: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image version to isolate goss testing to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_variant: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image type to isolate goss testing to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_os: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image OS to isolate goss testing to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_platform: Annotated[
                Optional[str],
                typer.Option(
                    show_default=SETTINGS.get_host_architecture(),
                    help="Filters which image build platform to run tests for, e.g. 'linux/amd64'.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            dev_versions: Annotated[
                Optional[DevVersionInclusionEnum],
                typer.Option(
                    help="Include or exclude development versions defined in config.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = DevVersionInclusionEnum.EXCLUDE,
            matrix_versions: Annotated[
                Optional[MatrixVersionInclusionEnum],
                typer.Option(
                    help="Include or exclude versions defined in image matrix.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = MatrixVersionInclusionEnum.EXCLUDE,
            metadata_file: Annotated[
                Optional[Path],
                typer.Option(
                    help="Path to a build metadata file. If given, attempts to run tests against image artifacts in the file."
                ),
            ] = None,
            clean: Annotated[
                Optional[bool],
                typer.Option(help="Clean up intermediary and temporary files after building."),
            ] = True,
        ) -> None:
            """Runs dgoss tests against images in the context path"""
            image_platform = image_platform or SETTINGS.architecture
            image_platform = f"linux/{image_platform}"

            settings = BakerySettings(
                filter=BakeryConfigFilter(
                    image_name=image_name,
                    image_version=re.escape(image_version) if image_version else None,
                    image_variant=image_variant,
                    image_os=image_os,
                    image_platform=[image_platform],
                ),
                dev_versions=dev_versions,
                matrix_versions=matrix_versions,
                clean_temporary=clean,
            )
            c = BakeryConfig.from_context(context, settings)

            if metadata_file:
                c.load_build_metadata_from_file(metadata_file)

            results = self.execute(c.base_path, c.targets, platform=image_platform)

            # Reconstruct report collection for table display
            report_collection = GossJsonReportCollection()
            has_errors = False
            for result in results:
                if result.artifacts and "report" in result.artifacts:
                    report_collection.add_report(result.target, result.artifacts["report"])
                if result.exit_code != 0 and result.artifacts and result.artifacts.get("execution_error"):
                    has_errors = True

            stderr_console.print(report_collection.table())
            if report_collection.test_failures:
                stderr_console.print("-" * 80)
                for uid, failures in report_collection.test_failures.items():
                    stderr_console.print(f"{uid} test failures:", style="error")
                    for failed_result in failures:
                        stderr_console.print(f"  - {failed_result.summary_line_compact}", style="error")
                stderr_console.print(f"❌ dgoss test(s) failed", style="error")
            if has_errors:
                stderr_console.print("-" * 80)
                for result in results:
                    if result.exit_code != 0 and result.artifacts and result.artifacts.get("execution_error"):
                        stderr_console.print(str(result.artifacts["execution_error"]), style="error")
                stderr_console.print(f"❌ dgoss command(s) failed to execute", style="error")
            if report_collection.test_failures or has_errors:
                raise typer.Exit(code=1)

            stderr_console.print(f"✅ Tests completed", style="success")

        app.add_typer(
            dgoss_app,
            name="dgoss",
            help="Run Goss tests against container images",
        )

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        platform: str | None = None,
        **kwargs,
    ) -> list[ToolCallResult]:
        """Execute dgoss tests against the given targets."""
        suite = DGossSuite(base_path, targets, platform=platform)
        report_collection, errors = suite.run()

        results = []
        # Build a lookup of errors by target for matching
        error_list = []
        if errors is not None:
            if isinstance(errors, BakeryToolRuntimeErrorGroup):
                error_list = list(errors.exceptions)
            else:
                error_list = [errors]

        for target in targets:
            # Find the report for this target
            report = None
            if target.image_name in report_collection:
                target_reports = report_collection[target.image_name]
                if target.uid in target_reports:
                    _, report = target_reports[target.uid]

            # Find any error for this target
            target_error = None
            for err in error_list:
                if hasattr(err, "message") and str(target) in err.message:
                    target_error = err
                    break

            exit_code = 0
            if target_error is not None:
                exit_code = getattr(target_error, "exit_code", 1)
            elif report is not None and report.summary.failed_count > 0:
                exit_code = 1

            artifacts = {}
            if report is not None:
                artifacts["report"] = report
            if target_error is not None:
                artifacts["execution_error"] = target_error

            results.append(
                ToolCallResult(
                    exit_code=exit_code,
                    tool_name="dgoss",
                    target=target,
                    stdout="",
                    stderr="",
                    artifacts=artifacts if artifacts else None,
                )
            )

        return results
```

Note: Add the missing import at the top of the file — `ExceptionGroup` is a builtin in Python 3.11+; for 3.10 compatibility, use a try/except or check. Since the project requires `>=3.10`, and `ExceptionGroup` was added in 3.11, but the existing code already uses `ExceptionGroup` in `error.py` (as `BakeryToolRuntimeErrorGroup(ExceptionGroup)`), this is consistent with the existing codebase.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd posit-bakery && python -m pytest test/plugins/test_registry.py::TestDGossPlugin -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add posit_bakery/plugins/builtin/dgoss/__init__.py test/plugins/test_registry.py
git commit -m "feat: implement DGossPlugin with CLI registration and execute method"
```

---

### Task 8: Register the plugin via entry points and wire CLI startup

**Files:**
- Modify: `pyproject.toml`
- Modify: `posit_bakery/cli/main.py`

- [ ] **Step 1: Add entry point to pyproject.toml**

Add after the `[project.scripts]` section in `pyproject.toml`:

```toml
[project.entry-points."bakery.plugins"]
dgoss = "posit_bakery.plugins.builtin.dgoss:DGossPlugin"
```

- [ ] **Step 2: Wire plugin discovery into CLI startup**

In `posit_bakery/cli/main.py`, add the import and plugin registration after the existing command registrations. Add at the top of the imports:

```python
from posit_bakery.plugins.registry import discover_plugins
```

Add at the bottom of the file (after the last `app.command` call, replacing the duplicate version line):

```python
# Discover and register plugins
for _name, _plugin in discover_plugins().items():
    _plugin.register_cli(app)
```

- [ ] **Step 3: Reinstall the package so entry points are registered**

Run: `cd posit-bakery && pip install -e .`

- [ ] **Step 4: Verify the dgoss plugin is discoverable**

Run: `cd posit-bakery && python -m pytest test/plugins/test_registry.py -v`
Expected: All registry tests PASS (including `TestDiscoverPlugins.test_discovers_dgoss_plugin`).

- [ ] **Step 5: Verify the CLI shows the dgoss command group**

Run: `cd posit-bakery && bakery dgoss --help`
Expected: Shows the dgoss command group with `run` subcommand.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml posit_bakery/cli/main.py
git commit -m "feat: register dgoss plugin via entry points and wire CLI startup"
```

---

### Task 9: Add deprecation bridge for `bakery run dgoss`

**Files:**
- Modify: `posit_bakery/cli/run.py`

- [ ] **Step 1: Replace the dgoss command body with a deprecation wrapper**

Replace the entire contents of `posit_bakery/cli/run.py` with:

```python
import logging
import re
import warnings
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.cli.common import with_verbosity_flags
from posit_bakery.config import BakeryConfig
from posit_bakery.config.config import BakeryConfigFilter, BakerySettings
from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
from posit_bakery.log import stderr_console
from posit_bakery.plugins.registry import get_plugin
from posit_bakery.settings import SETTINGS
from posit_bakery.util import auto_path

log = logging.getLogger(__name__)

app = typer.Typer(no_args_is_help=True)


class RichHelpPanelEnum(str, Enum):
    """Enum for categorizing options into rich help panels."""

    FILTERS = "Filters"


@app.command()
@with_verbosity_flags
def dgoss(
    context: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            writable=True,
            resolve_path=True,
            help="The root path to use. Defaults to the current working directory where invoked.",
        ),
    ] = auto_path(),
    image_name: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="The image name to isolate goss testing to.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    image_version: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="The image version to isolate goss testing to.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    image_variant: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="The image type to isolate goss testing to.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    image_os: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="The image OS to isolate goss testing to.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    image_platform: Annotated[
        Optional[str],
        typer.Option(
            show_default=SETTINGS.get_host_architecture(),
            help="Filters which image build platform to run tests for, e.g. 'linux/amd64'. Image test targets "
            "incompatible with the given platform(s) will be skipped. Requires a compatible goss binary.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    dev_versions: Annotated[
        Optional[DevVersionInclusionEnum],
        typer.Option(
            help="Include or exclude development versions defined in config.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = DevVersionInclusionEnum.EXCLUDE,
    matrix_versions: Annotated[
        Optional[MatrixVersionInclusionEnum],
        typer.Option(
            help="Include or exclude versions defined in image matrix.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = MatrixVersionInclusionEnum.EXCLUDE,
    metadata_file: Annotated[
        Optional[Path],
        typer.Option(
            help="Path to a build metadata file. If given, attempts to run tests against image artifacts in the file."
        ),
    ] = None,
    clean: Annotated[
        Optional[bool],
        typer.Option(help="Clean up intermediary and temporary files after building. Can be helpful for debugging."),
    ] = True,
) -> None:
    """Runs dgoss tests against images in the context path

    \b
    DEPRECATED: Use 'bakery dgoss run' instead.
    """
    warnings.warn(
        "'bakery run dgoss' is deprecated. Use 'bakery dgoss run' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    stderr_console.print(
        "[yellow]Warning: 'bakery run dgoss' is deprecated. Use 'bakery dgoss run' instead.[/yellow]"
    )

    # Autoselect host architecture platform if not specified.
    image_platform = image_platform or SETTINGS.architecture
    image_platform = f"linux/{image_platform}"

    settings = BakerySettings(
        filter=BakeryConfigFilter(
            image_name=image_name,
            image_version=re.escape(image_version) if image_version else None,
            image_variant=image_variant,
            image_os=image_os,
            image_platform=[image_platform],
        ),
        dev_versions=dev_versions,
        matrix_versions=matrix_versions,
        clean_temporary=clean,
    )
    c = BakeryConfig.from_context(context, settings)

    if metadata_file:
        c.load_build_metadata_from_file(metadata_file)

    dgoss_plugin = get_plugin("dgoss")
    results = dgoss_plugin.execute(c.base_path, c.targets, platform=image_platform)

    # Reconstruct report collection for table display
    from posit_bakery.plugins.builtin.dgoss.report import GossJsonReportCollection

    report_collection = GossJsonReportCollection()
    has_errors = False
    for result in results:
        if result.artifacts and "report" in result.artifacts:
            report_collection.add_report(result.target, result.artifacts["report"])
        if result.exit_code != 0 and result.artifacts and result.artifacts.get("execution_error"):
            has_errors = True

    stderr_console.print(report_collection.table())
    if report_collection.test_failures:
        stderr_console.print("-" * 80)
        for uid, failures in report_collection.test_failures.items():
            stderr_console.print(f"{uid} test failures:", style="error")
            for failed_result in failures:
                stderr_console.print(f"  - {failed_result.summary_line_compact}", style="error")
        stderr_console.print(f"❌ dgoss test(s) failed", style="error")
    if has_errors:
        stderr_console.print("-" * 80)
        stderr_console.print(f"❌ dgoss command(s) failed to execute", style="error")
    if report_collection.test_failures or has_errors:
        raise typer.Exit(code=1)

    stderr_console.print(f"✅ Tests completed", style="success")
```

- [ ] **Step 2: Verify the deprecation wrapper works**

Run: `cd posit-bakery && bakery run dgoss --help`
Expected: Shows the dgoss command help (should still work).

- [ ] **Step 3: Commit**

```bash
git add posit_bakery/cli/run.py
git commit -m "feat: add deprecation bridge for 'bakery run dgoss'"
```

---

### Task 10: Decouple config.py from goss module

**Files:**
- Modify: `posit_bakery/config/config.py`

- [ ] **Step 1: Update config.py imports and dgoss_targets method**

In `posit_bakery/config/config.py`, make these changes:

**Remove these imports** (lines 39-40):
```python
from posit_bakery.image.goss.dgoss import DGossSuite
from posit_bakery.image.goss.report import GossJsonReportCollection
```

**Add this import** in their place:
```python
from posit_bakery.plugins.registry import get_plugin
```

**Replace the `dgoss_targets` method** (lines 987-996) with:

```python
    def dgoss_targets(
        self,
        platform: str | None = None,
    ):
        """Run dgoss tests for all image targets via the dgoss plugin.

        :return: A list of ToolCallResult from the dgoss plugin.
        """
        dgoss_plugin = get_plugin("dgoss")
        return dgoss_plugin.execute(self.base_path, self.targets, platform=platform)
```

Note: The return type changes from `tuple[GossJsonReportCollection, error]` to `list[ToolCallResult]`. Since the only caller (`cli/run.py`) has already been updated to use the plugin directly via the deprecation bridge, this method is now only used by code that goes through the plugin path.

- [ ] **Step 2: Verify imports work**

Run: `cd posit-bakery && python -c "from posit_bakery.config.config import BakeryConfig; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add posit_bakery/config/config.py
git commit -m "refactor: decouple config.py from goss module, use plugin registry"
```

---

### Task 11: Remove BakeryDGossError from error.py

**Files:**
- Modify: `posit_bakery/error.py`

- [ ] **Step 1: Remove BakeryDGossError class**

Remove lines 156-188 from `posit_bakery/error.py` (the entire `BakeryDGossError` class). Keep everything else.

- [ ] **Step 2: Verify no remaining references to the old location**

Run: `cd posit-bakery && grep -r "from posit_bakery.error import.*BakeryDGossError" posit_bakery/ --include="*.py"`
Expected: No output (no remaining imports of `BakeryDGossError` from the old location).

- [ ] **Step 3: Commit**

```bash
git add posit_bakery/error.py
git commit -m "refactor: remove BakeryDGossError from error.py (moved to dgoss plugin)"
```

---

### Task 12: Remove old goss module and tests

**Files:**
- Remove: `posit_bakery/image/goss/__init__.py`
- Remove: `posit_bakery/image/goss/dgoss.py`
- Remove: `posit_bakery/image/goss/report.py`
- Remove: `test/image/goss/__init__.py`
- Remove: `test/image/goss/test_dgoss.py`
- Remove: `test/image/goss/test_report.py`
- Remove: `test/image/goss/testdata/basic_metadata.json`

- [ ] **Step 1: Verify no remaining imports from the old module**

Run: `cd posit-bakery && grep -r "from posit_bakery.image.goss" posit_bakery/ --include="*.py"`
Expected: No output.

Run: `cd posit-bakery && grep -r "from posit_bakery.image import.*DGossSuite\|from posit_bakery.image import.*GossJsonReportCollection" posit_bakery/ --include="*.py"`
Expected: No output.

- [ ] **Step 2: Remove old files**

```bash
git rm posit_bakery/image/goss/__init__.py posit_bakery/image/goss/dgoss.py posit_bakery/image/goss/report.py
git rm test/image/goss/__init__.py test/image/goss/test_dgoss.py test/image/goss/test_report.py
git rm test/image/goss/testdata/basic_metadata.json
```

- [ ] **Step 3: Check if `posit_bakery/image/goss/` directory is now empty and remove it**

```bash
rmdir posit_bakery/image/goss test/image/goss/testdata test/image/goss 2>/dev/null || true
```

- [ ] **Step 4: Update `posit_bakery/image/__init__.py` if it re-exports goss types**

Check `posit_bakery/image/__init__.py` — if it imports from `.goss`, remove those imports.

- [ ] **Step 5: Run the full test suite to verify nothing is broken**

Run: `cd posit-bakery && python -m pytest test/ -v --ignore=test/image/goss -k "not slow"`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: remove old goss module and tests (replaced by dgoss plugin)"
```

---

### Task 13: Final verification

- [ ] **Step 1: Run the full non-slow test suite**

Run: `cd posit-bakery && python -m pytest test/ -v -k "not slow"`
Expected: All tests PASS.

- [ ] **Step 2: Verify CLI works end-to-end**

Run: `cd posit-bakery && bakery --help`
Expected: Shows all commands including `dgoss` group.

Run: `cd posit-bakery && bakery dgoss --help`
Expected: Shows the `dgoss` command group with `run` subcommand.

Run: `cd posit-bakery && bakery dgoss run --help`
Expected: Shows all the filtering options.

- [ ] **Step 3: Verify deprecation bridge**

Run: `cd posit-bakery && bakery run dgoss --help`
Expected: Still works, shows the deprecated command help.

- [ ] **Step 4: Commit any remaining fixes**

If any tests failed or fixes were needed, commit them:

```bash
git add -A
git commit -m "fix: address issues found during final verification"
```
