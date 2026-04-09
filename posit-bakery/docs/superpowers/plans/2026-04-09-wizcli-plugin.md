# WizCLI Bakery Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Bakery plugin that runs `wizcli scan container-image` against image targets, with ToolOptions support, a Rich summary table of vulnerability severity counts, and proper exit code handling.

**Architecture:** Follows the existing dgoss plugin pattern — a plugin class satisfying `BakeryToolPlugin` protocol, a Pydantic command builder, a suite runner, lightweight report models, and entry point registration. The plugin surfaces CLI options for auth/scan configuration and ToolOptions for per-image/variant YAML config.

**Tech Stack:** Python 3.10+, Pydantic v2, Typer, Rich, subprocess

---

## File Structure

| File | Responsibility |
|---|---|
| `posit_bakery/plugins/builtin/wizcli/__init__.py` | `WizCLIPlugin` class: `register_cli`, `execute`, `results` |
| `posit_bakery/plugins/builtin/wizcli/options.py` | `WizCLIOptions(ToolOptions)` for bakery.yaml parsing |
| `posit_bakery/plugins/builtin/wizcli/command.py` | `WizCLICommand` Pydantic model: binary discovery, `.wiz` lookup, command list construction |
| `posit_bakery/plugins/builtin/wizcli/report.py` | `WizScanReport`, `WizScanReportCollection` with Rich table |
| `posit_bakery/plugins/builtin/wizcli/errors.py` | `BakeryWizCLIError(BakeryToolRuntimeError)` |
| `posit_bakery/plugins/builtin/wizcli/suite.py` | `WizCLISuite`: runs commands, writes results, collects reports |
| `pyproject.toml` | Entry point registration |
| `test/plugins/builtin/wizcli/conftest.py` | Test fixtures |
| `test/plugins/builtin/wizcli/__init__.py` | Package marker |
| `test/plugins/builtin/wizcli/test_options.py` | `WizCLIOptions.update()` tests |
| `test/plugins/builtin/wizcli/test_command.py` | `WizCLICommand` construction and command list tests |
| `test/plugins/builtin/wizcli/test_report.py` | Report parsing and table generation tests |
| `test/plugins/builtin/wizcli/testdata/` | Sample JSON output and metadata files |

---

### Task 1: WizCLIOptions — ToolOptions for bakery.yaml

**Files:**
- Create: `posit_bakery/plugins/builtin/wizcli/__init__.py` (empty, just package marker)
- Create: `posit_bakery/plugins/builtin/wizcli/options.py`
- Create: `test/plugins/builtin/wizcli/__init__.py` (empty)
- Create: `test/plugins/builtin/wizcli/test_options.py`

- [ ] **Step 1: Create package markers**

```python
# posit_bakery/plugins/builtin/wizcli/__init__.py
# (empty file — will be populated in Task 6)
```

```python
# test/plugins/builtin/wizcli/__init__.py
# (empty file)
```

- [ ] **Step 2: Write failing tests for WizCLIOptions**

Create `test/plugins/builtin/wizcli/test_options.py`:

```python
import pytest
from _pytest.mark import ParameterSet

from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions

pytestmark = [
    pytest.mark.unit,
    pytest.mark.wizcli,
]


class TestWizCLIOptions:
    def test_defaults(self):
        opts = WizCLIOptions()
        assert opts.tool == "wizcli"
        assert opts.projects is None
        assert opts.policies is None
        assert opts.tags is None
        assert opts.scanOsManagedLibraries is None
        assert opts.scanGoStandardLibrary is None

    def test_explicit_values(self):
        opts = WizCLIOptions(
            projects=["proj-1"],
            policies=["pol-1"],
            tags=["team=platform"],
            scanOsManagedLibraries=True,
            scanGoStandardLibrary=False,
        )
        assert opts.projects == ["proj-1"]
        assert opts.policies == ["pol-1"]
        assert opts.tags == ["team=platform"]
        assert opts.scanOsManagedLibraries is True
        assert opts.scanGoStandardLibrary is False

    @staticmethod
    def merge_params() -> list[ParameterSet]:
        return [
            pytest.param({}, {}, {
                "projects": None, "policies": None, "tags": None,
                "scanOsManagedLibraries": None, "scanGoStandardLibrary": None,
            }, id="both_default"),
            pytest.param({}, {"projects": ["p1"], "policies": ["pol1"]}, {
                "projects": ["p1"], "policies": ["pol1"], "tags": None,
                "scanOsManagedLibraries": None, "scanGoStandardLibrary": None,
            }, id="left_default_right_set"),
            pytest.param({"projects": ["p2"], "scanOsManagedLibraries": True}, {}, {
                "projects": ["p2"], "policies": None, "tags": None,
                "scanOsManagedLibraries": True, "scanGoStandardLibrary": None,
            }, id="left_set_right_default"),
            pytest.param(
                {"projects": ["p2"], "tags": ["env=ci"]},
                {"projects": ["p1"], "tags": ["env=prod"], "scanGoStandardLibrary": True},
                {"projects": ["p2"], "policies": None, "tags": ["env=ci"],
                 "scanOsManagedLibraries": None, "scanGoStandardLibrary": True},
                id="left_wins_when_set",
            ),
        ]

    @pytest.mark.parametrize("left,right,expected", merge_params())
    def test_update(self, left, right, expected):
        left_options = WizCLIOptions(**left)
        right_options = WizCLIOptions(**right)
        merged = left_options.update(right_options)

        for key, value in expected.items():
            assert getattr(merged, key) == value, (
                f"Expected {key} to be {value}, got {getattr(merged, key)}"
            )
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd posit-bakery && uv run pytest test/plugins/builtin/wizcli/test_options.py -v`
Expected: ImportError — `posit_bakery.plugins.builtin.wizcli.options` does not exist.

- [ ] **Step 4: Implement WizCLIOptions**

Create `posit_bakery/plugins/builtin/wizcli/options.py`:

```python
from copy import deepcopy
from typing import Annotated, Literal

from pydantic import Field

from posit_bakery.config.tools.base import ToolOptions


class WizCLIOptions(ToolOptions):
    """Configuration options for WizCLI container image scanning."""

    tool: Literal["wizcli"] = "wizcli"
    projects: Annotated[
        list[str] | None,
        Field(default=None, description="Wiz project IDs or slugs to scope the scan to."),
    ] = None
    policies: Annotated[
        list[str] | None,
        Field(default=None, description="Policies to apply to the scan."),
    ] = None
    tags: Annotated[
        list[str] | None,
        Field(default=None, description="Tags to mark the scan with (KEY or KEY=VALUE)."),
    ] = None
    scanOsManagedLibraries: Annotated[
        bool | None,
        Field(default=None, description="Enable or disable scanning of OS-package managed code libraries."),
    ] = None
    scanGoStandardLibrary: Annotated[
        bool | None,
        Field(default=None, description="Enable or disable scanning of Go standard library."),
    ] = None

    def update(self, other: "WizCLIOptions") -> "WizCLIOptions":
        """Update this instance with settings from another.

        The merge strategy uses the values of the other instance for any field not explicitly set
        in the current instance.
        """
        merged = deepcopy(self)
        for field_name in ("projects", "policies", "tags", "scanOsManagedLibraries", "scanGoStandardLibrary"):
            if field_name not in self.model_fields_set:
                setattr(merged, field_name, getattr(other, field_name))
        return merged
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd posit-bakery && uv run pytest test/plugins/builtin/wizcli/test_options.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add posit_bakery/plugins/builtin/wizcli/__init__.py posit_bakery/plugins/builtin/wizcli/options.py test/plugins/builtin/wizcli/__init__.py test/plugins/builtin/wizcli/test_options.py
git commit -m "feat(wizcli): add WizCLIOptions for bakery.yaml tool configuration"
```

---

### Task 2: BakeryWizCLIError

**Files:**
- Create: `posit_bakery/plugins/builtin/wizcli/errors.py`

- [ ] **Step 1: Implement BakeryWizCLIError**

Create `posit_bakery/plugins/builtin/wizcli/errors.py`:

```python
import textwrap
from typing import List

from posit_bakery.error import BakeryToolRuntimeError

# Exit code meanings for wizcli scan container-image
WIZCLI_EXIT_CODE_SUCCESS = 0
WIZCLI_EXIT_CODE_GENERAL_ERROR = 1
WIZCLI_EXIT_CODE_INVALID_COMMAND = 2
WIZCLI_EXIT_CODE_AUTH_ERROR = 3
WIZCLI_EXIT_CODE_POLICY_VIOLATION = 4

WIZCLI_EXIT_CODE_DESCRIPTIONS = {
    WIZCLI_EXIT_CODE_SUCCESS: "Passed",
    WIZCLI_EXIT_CODE_GENERAL_ERROR: "General error (timeout, network)",
    WIZCLI_EXIT_CODE_INVALID_COMMAND: "Invalid command (bad syntax or parameters)",
    WIZCLI_EXIT_CODE_AUTH_ERROR: "Authentication error",
    WIZCLI_EXIT_CODE_POLICY_VIOLATION: "Security issues violate policy",
}


class BakeryWizCLIError(BakeryToolRuntimeError):
    def __init__(
        self,
        message: str = None,
        tool_name: str = None,
        cmd: List[str] = None,
        stdout: str | bytes | None = None,
        stderr: str | bytes | None = None,
        exit_code: int = 1,
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

    def __str__(self) -> str:
        s = f"{self.message}\n"
        s += f"  - Exit code: {self.exit_code}"
        desc = WIZCLI_EXIT_CODE_DESCRIPTIONS.get(self.exit_code)
        if desc:
            s += f" ({desc})"
        s += "\n"
        stderr_dump = self.dump_stderr()
        if stderr_dump:
            s += f"  - stderr:\n{textwrap.indent(stderr_dump, '      ')}\n"
        s += f"  - Command executed: {' '.join(self.cmd)}\n"
        if self.metadata:
            s += "  - Metadata:\n"
            for key, value in self.metadata.items():
                s += f"    - {key}: {value}\n"
        return s
```

- [ ] **Step 2: Commit**

```bash
git add posit_bakery/plugins/builtin/wizcli/errors.py
git commit -m "feat(wizcli): add BakeryWizCLIError with exit code descriptions"
```

---

### Task 3: WizScanReport and WizScanReportCollection

**Files:**
- Create: `posit_bakery/plugins/builtin/wizcli/report.py`
- Create: `test/plugins/builtin/wizcli/test_report.py`
- Create: `test/plugins/builtin/wizcli/testdata/scan_result.json` (copy from `../images-workbench/workbench-session-init.json`)

- [ ] **Step 1: Copy test data**

Copy the sample wizcli JSON output for use in tests:

```bash
cp ../images-workbench/workbench-session-init.json posit-bakery/test/plugins/builtin/wizcli/testdata/scan_result.json
```

- [ ] **Step 2: Write failing tests for report models**

Create `test/plugins/builtin/wizcli/test_report.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from posit_bakery.plugins.builtin.wizcli.report import WizScanReport, WizScanReportCollection

pytestmark = [
    pytest.mark.unit,
    pytest.mark.wizcli,
]

WIZCLI_TESTDATA_DIR = (Path(__file__).parent / "testdata").absolute()


class TestWizScanReport:
    def test_load_from_file(self):
        report = WizScanReport.load(WIZCLI_TESTDATA_DIR / "scan_result.json")
        assert report.scan_id == "0069d6c0-7d0b-85d5-9028-affa6e2f8001"
        assert report.status_state == "SUCCESS"
        assert report.status_verdict == "WARN_BY_POLICY"
        assert report.critical_count == 4
        assert report.high_count == 210
        assert report.medium_count == 195
        assert report.low_count == 39
        assert report.info_count == 0

    def test_report_url_non_url_is_none(self):
        """When reportUrl is a descriptive string (not a URL), report_url should be None."""
        report = WizScanReport.load(WIZCLI_TESTDATA_DIR / "scan_result.json")
        assert report.report_url is None

    def test_report_url_real_url(self, tmp_path):
        """When reportUrl is a real URL, report_url should return it."""
        data = json.loads((WIZCLI_TESTDATA_DIR / "scan_result.json").read_text())
        data["reportUrl"] = "https://app.wiz.io/reports/12345"
        result_file = tmp_path / "scan_result.json"
        result_file.write_text(json.dumps(data))
        report = WizScanReport.load(result_file)
        assert report.report_url == "https://app.wiz.io/reports/12345"

    def test_total_vulnerability_count(self):
        report = WizScanReport.load(WIZCLI_TESTDATA_DIR / "scan_result.json")
        assert report.total_count == 4 + 210 + 195 + 39 + 0

    def test_empty_vulnerabilities(self, tmp_path):
        """Report with no vulnerable artifacts should have zero counts."""
        data = json.loads((WIZCLI_TESTDATA_DIR / "scan_result.json").read_text())
        data["result"]["vulnerableSBOMArtifactsByNameVersion"] = []
        result_file = tmp_path / "empty.json"
        result_file.write_text(json.dumps(data))
        report = WizScanReport.load(result_file)
        assert report.critical_count == 0
        assert report.total_count == 0


class TestWizScanReportCollection:
    def _make_mock_target(self, image_name, uid, version="1.0.0", variant=None, os_name=None):
        target = MagicMock()
        target.image_name = image_name
        target.uid = uid
        target.image_version.name = version
        target.image_variant = None
        target.image_os = None
        if variant:
            target.image_variant = MagicMock()
            target.image_variant.name = variant
        if os_name:
            target.image_os = MagicMock()
            target.image_os.name = os_name
        return target

    def test_add_report(self):
        collection = WizScanReportCollection()
        target = self._make_mock_target("connect", "connect-1.0.0-std-ubuntu2204")
        report = WizScanReport.load(WIZCLI_TESTDATA_DIR / "scan_result.json")
        collection.add_report(target, report)

        assert "connect" in collection
        assert "connect-1.0.0-std-ubuntu2204" in collection["connect"]

    def test_aggregate(self):
        collection = WizScanReportCollection()
        target = self._make_mock_target("connect", "connect-1.0.0", "1.0.0", "Standard", "Ubuntu 22.04")
        report = WizScanReport.load(WIZCLI_TESTDATA_DIR / "scan_result.json")
        collection.add_report(target, report)

        agg = collection.aggregate()
        assert agg["total"]["critical"] == 4
        assert agg["total"]["high"] == 210
        assert agg["total"]["medium"] == 195
        assert agg["total"]["low"] == 39
        assert agg["total"]["info"] == 0

    def test_table_returns_rich_table(self):
        collection = WizScanReportCollection()
        target = self._make_mock_target("connect", "connect-1.0.0", "1.0.0", "Standard", "Ubuntu 22.04")
        report = WizScanReport.load(WIZCLI_TESTDATA_DIR / "scan_result.json")
        collection.add_report(target, report)

        table = collection.table()
        assert table.title == "WizCLI Scan Results"
        # Verify column count: Image, Version, Variant, OS, Verdict, Critical, High, Medium, Low, Info, Report URL
        assert len(table.columns) == 11
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd posit-bakery && uv run pytest test/plugins/builtin/wizcli/test_report.py -v`
Expected: ImportError — `posit_bakery.plugins.builtin.wizcli.report` does not exist.

- [ ] **Step 4: Implement report models**

Create `posit_bakery/plugins/builtin/wizcli/report.py`:

```python
import json
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field
from rich.table import Table
from rich.text import Text

from posit_bakery.image.image_target import ImageTarget


class WizScanReport(BaseModel):
    """Lightweight model for wizcli scan JSON output.

    Captures scan metadata and aggregated vulnerability severity counts without modeling
    the full wizcli JSON schema.
    """

    filepath: Annotated[Path | None, Field(default=None, exclude=True)]
    scan_id: str
    status_state: str
    status_verdict: str
    report_url: str | None
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0

    @property
    def total_count(self) -> int:
        return self.critical_count + self.high_count + self.medium_count + self.low_count + self.info_count

    @classmethod
    def load(cls, filepath: Path) -> "WizScanReport":
        """Load a WizScanReport from a wizcli JSON output file."""
        with filepath.open("r") as f:
            data = json.load(f)

        # Aggregate severity counts from vulnerable SBOM artifacts
        critical = high = medium = low = info = 0
        for artifact in data.get("result", {}).get("vulnerableSBOMArtifactsByNameVersion", []) or []:
            severities = artifact.get("vulnerabilityFindings", {}).get("severities", {})
            critical += severities.get("criticalCount", 0)
            high += severities.get("highCount", 0)
            medium += severities.get("mediumCount", 0)
            low += severities.get("lowCount", 0)
            info += severities.get("infoCount", 0)

        # Only treat reportUrl as a real URL if it starts with http
        raw_url = data.get("reportUrl")
        report_url = raw_url if raw_url and raw_url.startswith("http") else None

        return cls(
            filepath=filepath,
            scan_id=data["id"],
            status_state=data["status"]["state"],
            status_verdict=data["status"]["verdict"],
            report_url=report_url,
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            low_count=low,
            info_count=info,
        )


class WizScanReportCollection(dict):
    """Collection of WizScanReports keyed by image_name -> {uid: (target, report)}."""

    def add_report(self, image_target: ImageTarget, report: WizScanReport):
        self.setdefault(image_target.image_name, dict())[image_target.uid] = (image_target, report)

    def aggregate(self) -> dict:
        totals = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        results = {"total": totals}

        for image_name, targets in self.items():
            for uid, (target, report) in targets.items():
                variant_name = target.image_variant.name if target.image_variant else ""
                os_name = target.image_os.name if target.image_os else ""
                version_name = target.image_version.name

                row = {
                    "critical": report.critical_count,
                    "high": report.high_count,
                    "medium": report.medium_count,
                    "low": report.low_count,
                    "info": report.info_count,
                    "verdict": report.status_verdict,
                    "report_url": report.report_url,
                }

                results.setdefault(image_name, {})
                results[image_name].setdefault(version_name, {})
                results[image_name][version_name].setdefault(os_name, {})
                results[image_name][version_name][os_name][variant_name] = row

                for key in totals:
                    totals[key] += row[key]

        return results

    def table(self) -> Table:
        aggregated = self.aggregate()
        total_row = aggregated.pop("total")

        table = Table(title="WizCLI Scan Results")
        table.add_column("Image Name", justify="left")
        table.add_column("Version", justify="left")
        table.add_column("Variant", justify="left")
        table.add_column("OS", justify="left")
        table.add_column("Verdict", justify="left")
        table.add_column("Critical", justify="right", header_style="bright_red")
        table.add_column("High", justify="right", header_style="red")
        table.add_column("Medium", justify="right", header_style="yellow")
        table.add_column("Low", justify="right", header_style="bright_blue")
        table.add_column("Info", justify="right", header_style="bright_black")
        table.add_column("Report URL", justify="left")

        for image_name, versions in aggregated.items():
            p_image_name = image_name
            for version, oses in versions.items():
                p_version = version
                for os_name, variants in oses.items():
                    p_os = os_name
                    for variant_name, row in variants.items():
                        critical_style = "bright_red bold" if row["critical"] > 0 else "bright_black italic"
                        high_style = "red bold" if row["high"] > 0 else "bright_black italic"
                        medium_style = "yellow bold" if row["medium"] > 0 else "bright_black italic"
                        low_style = "bright_blue bold" if row["low"] > 0 else "bright_black italic"
                        info_style = "bright_black"

                        table.add_row(
                            p_image_name,
                            p_version,
                            variant_name,
                            p_os,
                            row["verdict"],
                            Text(str(row["critical"]), style=critical_style),
                            Text(str(row["high"]), style=high_style),
                            Text(str(row["medium"]), style=medium_style),
                            Text(str(row["low"]), style=low_style),
                            Text(str(row["info"]), style=info_style),
                            row.get("report_url") or "",
                        )
                        p_image_name = ""
                        p_version = ""
                        p_os = ""

        table.add_section()
        table.add_row(
            "Total", "", "", "", "",
            str(total_row["critical"]),
            str(total_row["high"]),
            str(total_row["medium"]),
            str(total_row["low"]),
            str(total_row["info"]),
            "",
        )

        return table
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd posit-bakery && uv run pytest test/plugins/builtin/wizcli/test_report.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add posit_bakery/plugins/builtin/wizcli/report.py test/plugins/builtin/wizcli/test_report.py test/plugins/builtin/wizcli/testdata/
git commit -m "feat(wizcli): add WizScanReport models with severity aggregation and Rich table"
```

---

### Task 4: WizCLICommand — Command Builder

**Files:**
- Create: `posit_bakery/plugins/builtin/wizcli/command.py`
- Create: `test/plugins/builtin/wizcli/conftest.py`
- Create: `test/plugins/builtin/wizcli/test_command.py`

- [ ] **Step 1: Write test fixtures**

Create `test/plugins/builtin/wizcli/conftest.py`:

```python
import pytest

from posit_bakery.image import ImageTarget


@pytest.fixture
def basic_standard_image_target(get_config_obj):
    """Return a standard ImageTarget object for testing."""
    basic_config_obj = get_config_obj("basic")

    image = basic_config_obj.model.get_image("test-image")
    version = image.get_version("1.0.0")
    variant = image.get_variant("Standard")
    os = version.os[0]

    return ImageTarget.new_image_target(
        repository=basic_config_obj.model.repository,
        image_version=version,
        image_variant=variant,
        image_os=os,
    )
```

- [ ] **Step 2: Write failing tests for WizCLICommand**

Create `test/plugins/builtin/wizcli/test_command.py`:

```python
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from posit_bakery.plugins.builtin.wizcli.command import WizCLICommand, find_wiz_config_file

pytestmark = [
    pytest.mark.unit,
    pytest.mark.wizcli,
]


class TestFindWizConfigFile:
    def test_finds_in_version_path(self, basic_standard_image_target, tmp_path):
        """Should find .wiz at version path level."""
        # Create .wiz in the version path
        wiz_file = basic_standard_image_target.context.version_path / ".wiz"
        wiz_file.touch()
        result = find_wiz_config_file(basic_standard_image_target.context)
        assert result == wiz_file

    def test_finds_in_image_path(self, basic_standard_image_target, tmp_path):
        """Should find .wiz at image path level when not at version level."""
        wiz_file = basic_standard_image_target.context.image_path / ".wiz"
        wiz_file.touch()
        result = find_wiz_config_file(basic_standard_image_target.context)
        assert result == wiz_file

    def test_returns_none_when_not_found(self, basic_standard_image_target):
        """Should return None when .wiz not found at version or image level."""
        result = find_wiz_config_file(basic_standard_image_target.context)
        assert result is None


class TestWizCLICommand:
    def test_from_image_target_basic(self, basic_standard_image_target):
        """Test basic initialization from an image target."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
        )
        assert cmd.image_target == basic_standard_image_target
        assert str(basic_standard_image_target.containerfile) in cmd.command
        assert "--no-color" in cmd.command
        assert "--no-style" in cmd.command
        assert "--json-output-file" in " ".join(cmd.command)

    def test_command_includes_dockerfile(self, basic_standard_image_target):
        """Test that --dockerfile is set to the target's containerfile."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
        )
        idx = cmd.command.index("--dockerfile")
        assert cmd.command[idx + 1] == str(basic_standard_image_target.containerfile)

    def test_command_with_cli_options(self, basic_standard_image_target):
        """Test that CLI options are passed through to the command."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            disabled_scanners="Secret,Malware",
            driver="mount",
            timeout="30m",
            no_publish=True,
        )
        assert "--disabled-scanners" in cmd.command
        assert "Secret,Malware" in cmd.command
        assert "--driver" in cmd.command
        assert "mount" in cmd.command
        assert "--timeout" in cmd.command
        assert "30m" in cmd.command
        assert "--no-publish" in cmd.command

    def test_command_with_tool_options(self, basic_standard_image_target):
        """Test that ToolOptions fields are included in the command."""
        from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            tool_options=WizCLIOptions(
                projects=["proj-1", "proj-2"],
                policies=["pol-1"],
                tags=["team=platform"],
                scanOsManagedLibraries=True,
                scanGoStandardLibrary=False,
            ),
        )
        command_str = " ".join(cmd.command)
        assert "--projects" in command_str
        assert "proj-1,proj-2" in command_str
        assert "--policies" in command_str
        assert "pol-1" in command_str
        assert "--tags" in command_str
        assert "team=platform" in command_str
        assert "--scan-os-managed-libraries=true" in command_str
        assert "--scan-go-standard-library=false" in command_str

    def test_command_with_auth_options(self, basic_standard_image_target):
        """Test that auth CLI options are passed through."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            client_id="my-id",
            client_secret="my-secret",
        )
        assert "--client-id" in cmd.command
        assert "my-id" in cmd.command
        assert "--client-secret" in cmd.command
        assert "my-secret" in cmd.command

    def test_command_with_device_code_flags(self, basic_standard_image_target):
        """Test that boolean auth flags are included when set."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            use_device_code=True,
            no_browser=True,
        )
        assert "--use-device-code" in cmd.command
        assert "--no-browser" in cmd.command

    def test_validate_no_wizcli_bin(self, basic_standard_image_target):
        """Test that validation fails if wizcli binary cannot be found."""
        with patch("posit_bakery.plugins.builtin.wizcli.command.find_wizcli_bin") as mock:
            mock.return_value = None
            with pytest.raises(ValidationError, match="wizcli binary path must be specified"):
                results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
                WizCLICommand.from_image_target(
                    image_target=basic_standard_image_target,
                    results_dir=results_dir,
                )
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd posit-bakery && uv run pytest test/plugins/builtin/wizcli/test_command.py -v`
Expected: ImportError — `posit_bakery.plugins.builtin.wizcli.command` does not exist.

- [ ] **Step 4: Implement WizCLICommand**

Create `posit_bakery/plugins/builtin/wizcli/command.py`:

```python
from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, Field, computed_field, model_validator

from posit_bakery.image.image_target import ImageTarget, ImageTargetContext
from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions
from posit_bakery.util import find_bin


def find_wizcli_bin(context: ImageTargetContext) -> str | None:
    """Find the path to the wizcli binary."""
    return find_bin(context.base_path, "wizcli", "WIZCLI_PATH") or "wizcli"


def find_wiz_config_file(context: ImageTargetContext) -> Path | None:
    """Find a .wiz configuration file, checking version path then image path."""
    version_wiz = context.version_path / ".wiz"
    if version_wiz.exists():
        return version_wiz

    image_wiz = context.image_path / ".wiz"
    if image_wiz.exists():
        return image_wiz

    return None


class WizCLICommand(BaseModel):
    image_target: ImageTarget
    wizcli_bin: Annotated[str, Field(default_factory=lambda data: find_wizcli_bin(data["image_target"].context))]
    results_file: Path
    wiz_config_file: Annotated[
        Path | None, Field(default_factory=lambda data: find_wiz_config_file(data["image_target"].context))
    ]

    # ToolOptions fields
    tool_options: Annotated[WizCLIOptions | None, Field(default=None)]

    # CLI pass-through options
    disabled_scanners: Annotated[str | None, Field(default=None)]
    driver: Annotated[str | None, Field(default=None)]
    client_id: Annotated[str | None, Field(default=None)]
    client_secret: Annotated[str | None, Field(default=None)]
    use_device_code: Annotated[bool, Field(default=False)]
    no_browser: Annotated[bool, Field(default=False)]
    timeout: Annotated[str | None, Field(default=None)]
    no_publish: Annotated[bool, Field(default=False)]
    scan_context_id: Annotated[str | None, Field(default=None)]
    log_file: Annotated[str | None, Field(default=None)]

    @classmethod
    def from_image_target(
        cls,
        image_target: ImageTarget,
        results_dir: Path,
        *,
        tool_options: WizCLIOptions | None = None,
        disabled_scanners: str | None = None,
        driver: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        use_device_code: bool = False,
        no_browser: bool = False,
        timeout: str | None = None,
        no_publish: bool = False,
        scan_context_id: str | None = None,
        log_file: str | None = None,
    ) -> "WizCLICommand":
        # Resolve tool options from variant config if not explicitly provided
        if tool_options is None and image_target.image_variant:
            tool_options = image_target.image_variant.get_tool_option("wizcli")

        image_subdir = results_dir / image_target.image_name
        results_file = image_subdir / f"{image_target.uid}.json"

        return cls(
            image_target=image_target,
            results_file=results_file,
            tool_options=tool_options,
            disabled_scanners=disabled_scanners,
            driver=driver,
            client_id=client_id,
            client_secret=client_secret,
            use_device_code=use_device_code,
            no_browser=no_browser,
            timeout=timeout,
            no_publish=no_publish,
            scan_context_id=scan_context_id,
            log_file=log_file,
        )

    @model_validator(mode="after")
    def validate(self) -> Self:
        if not self.wizcli_bin:
            raise ValueError(
                "wizcli binary path must be specified with the `WIZCLI_PATH` environment variable if it cannot be "
                "discovered in the system PATH."
            )
        return self

    @computed_field
    @property
    def command(self) -> list[str]:
        cmd = [self.wizcli_bin, "scan", "container-image"]

        # Image reference
        cmd.append(self.image_target.ref())

        # Output file
        cmd.extend(["--json-output-file", str(self.results_file)])

        # Dockerfile
        cmd.extend(["--dockerfile", str(self.image_target.containerfile)])

        # Wiz configuration file (only if found at version or image level)
        if self.wiz_config_file:
            cmd.extend(["--wiz-configuration-file", str(self.wiz_config_file)])

        # Always set for machine-parseable output
        cmd.extend(["--no-color", "--no-style"])

        # ToolOptions fields
        if self.tool_options:
            if self.tool_options.projects:
                cmd.extend(["--projects", ",".join(self.tool_options.projects)])
            if self.tool_options.policies:
                cmd.extend(["--policies", ",".join(self.tool_options.policies)])
            if self.tool_options.tags:
                for tag in self.tool_options.tags:
                    cmd.extend(["--tags", tag])
            if self.tool_options.scanOsManagedLibraries is not None:
                cmd.append(f"--scan-os-managed-libraries={str(self.tool_options.scanOsManagedLibraries).lower()}")
            if self.tool_options.scanGoStandardLibrary is not None:
                cmd.append(f"--scan-go-standard-library={str(self.tool_options.scanGoStandardLibrary).lower()}")

        # CLI pass-through options
        if self.disabled_scanners:
            cmd.extend(["--disabled-scanners", self.disabled_scanners])
        if self.driver:
            cmd.extend(["--driver", self.driver])
        if self.client_id:
            cmd.extend(["--client-id", self.client_id])
        if self.client_secret:
            cmd.extend(["--client-secret", self.client_secret])
        if self.use_device_code:
            cmd.append("--use-device-code")
        if self.no_browser:
            cmd.append("--no-browser")
        if self.timeout:
            cmd.extend(["--timeout", self.timeout])
        if self.no_publish:
            cmd.append("--no-publish")
        if self.scan_context_id:
            cmd.extend(["--scan-context-id", self.scan_context_id])
        if self.log_file:
            cmd.extend(["--log", self.log_file])

        return cmd
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd posit-bakery && uv run pytest test/plugins/builtin/wizcli/test_command.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add posit_bakery/plugins/builtin/wizcli/command.py test/plugins/builtin/wizcli/conftest.py test/plugins/builtin/wizcli/test_command.py
git commit -m "feat(wizcli): add WizCLICommand builder with .wiz lookup and CLI/ToolOptions integration"
```

---

### Task 5: WizCLISuite — Suite Runner

**Files:**
- Create: `posit_bakery/plugins/builtin/wizcli/suite.py`

- [ ] **Step 1: Implement WizCLISuite**

Create `posit_bakery/plugins/builtin/wizcli/suite.py`:

```python
import logging
import os
import shutil
import subprocess
from pathlib import Path

from posit_bakery.error import BakeryToolRuntimeError, BakeryToolRuntimeErrorGroup
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.wizcli.command import WizCLICommand
from posit_bakery.plugins.builtin.wizcli.errors import (
    BakeryWizCLIError,
    WIZCLI_EXIT_CODE_POLICY_VIOLATION,
)
from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions
from posit_bakery.plugins.builtin.wizcli.report import WizScanReport, WizScanReportCollection
from posit_bakery.settings import SETTINGS

log = logging.getLogger(__name__)


class WizCLISuite:
    def __init__(
        self,
        context: Path,
        image_targets: list[ImageTarget],
        *,
        tool_options: WizCLIOptions | None = None,
        disabled_scanners: str | None = None,
        driver: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        use_device_code: bool = False,
        no_browser: bool = False,
        timeout: str | None = None,
        no_publish: bool = False,
        scan_context_id: str | None = None,
        log_file: str | None = None,
    ) -> None:
        self.context = context
        self.results_dir = context / "results" / "wizcli"

        self.wizcli_commands = [
            WizCLICommand.from_image_target(
                target,
                results_dir=self.results_dir,
                tool_options=tool_options,
                disabled_scanners=disabled_scanners,
                driver=driver,
                client_id=client_id,
                client_secret=client_secret,
                use_device_code=use_device_code,
                no_browser=no_browser,
                timeout=timeout,
                no_publish=no_publish,
                scan_context_id=scan_context_id,
                log_file=log_file,
            )
            for target in image_targets
        ]

    def run(self) -> tuple[WizScanReportCollection, BakeryToolRuntimeError | BakeryToolRuntimeErrorGroup | None]:
        if self.results_dir.exists():
            shutil.rmtree(self.results_dir)
        self.results_dir.mkdir(parents=True)

        report_collection = WizScanReportCollection()
        errors = []
        verbose = SETTINGS.log_level == logging.DEBUG

        for wizcli_command in self.wizcli_commands:
            log.info(f"[bright_blue bold]=== Scanning '{str(wizcli_command.image_target)}' with WizCLI ===")
            log.debug(f"[bright_black]Executing wizcli command: {' '.join(wizcli_command.command)}")

            # Ensure output directory exists
            wizcli_command.results_file.parent.mkdir(parents=True, exist_ok=True)

            run_env = os.environ.copy()

            if verbose:
                p = subprocess.run(wizcli_command.command, env=run_env, cwd=self.context, capture_output=True)
                try:
                    stdout_text = p.stdout.decode("utf-8").strip()
                    if stdout_text:
                        log.debug(f"[bright_black]wizcli stdout:\n{stdout_text}")
                except UnicodeDecodeError:
                    pass
                try:
                    stderr_text = p.stderr.decode("utf-8").strip()
                    if stderr_text:
                        log.debug(f"[bright_black]wizcli stderr:\n{stderr_text}")
                except UnicodeDecodeError:
                    pass
            else:
                p = subprocess.run(
                    wizcli_command.command,
                    env=run_env,
                    cwd=self.context,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            exit_code = p.returncode

            # Try to parse the results file written by wizcli
            report = None
            parse_err = None
            if wizcli_command.results_file.exists():
                try:
                    report = WizScanReport.load(wizcli_command.results_file)
                    report_collection.add_report(wizcli_command.image_target, report)
                except Exception as e:
                    log.error(
                        f"Failed to parse wizcli results for '{str(wizcli_command.image_target)}': {e}"
                    )
                    parse_err = e

            if exit_code != 0 and report is None:
                log.error(
                    f"wizcli for '{str(wizcli_command.image_target)}' exited with code {exit_code}"
                )
                errors.append(
                    BakeryWizCLIError(
                        f"wizcli scan failed for '{str(wizcli_command.image_target)}'",
                        "wizcli",
                        cmd=wizcli_command.command,
                        stdout=p.stdout if verbose else None,
                        stderr=p.stderr if verbose else None,
                        exit_code=exit_code,
                    )
                )
            elif exit_code == 0:
                log.info(f"[bright_green bold]Scan passed for '{str(wizcli_command.image_target)}'")
            elif exit_code == WIZCLI_EXIT_CODE_POLICY_VIOLATION:
                log.warning(
                    f"[yellow bold]Security policy violation for '{str(wizcli_command.image_target)}'"
                )
            else:
                log.warning(
                    f"[yellow bold]Scan completed with issues for '{str(wizcli_command.image_target)}' "
                    f"(exit code {exit_code})"
                )

        if errors:
            if len(errors) == 1:
                errors = errors[0]
            else:
                errors = BakeryToolRuntimeErrorGroup("wizcli runtime errors occurred for multiple images.", errors)
        else:
            errors = None

        return report_collection, errors
```

- [ ] **Step 2: Commit**

```bash
git add posit_bakery/plugins/builtin/wizcli/suite.py
git commit -m "feat(wizcli): add WizCLISuite runner with verbose/quiet output handling"
```

---

### Task 6: WizCLIPlugin — Plugin Class and CLI Registration

**Files:**
- Modify: `posit_bakery/plugins/builtin/wizcli/__init__.py`
- Modify: `pyproject.toml:33-35`

- [ ] **Step 1: Implement WizCLIPlugin**

Replace the contents of `posit_bakery/plugins/builtin/wizcli/__init__.py`:

```python
import logging
import re
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.cli.common import with_verbosity_flags
from posit_bakery.config.config import BakeryConfig, BakeryConfigFilter, BakerySettings
from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
from posit_bakery.error import BakeryToolRuntimeErrorGroup
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.log import stderr_console
from posit_bakery.plugins.builtin.wizcli.errors import WIZCLI_EXIT_CODE_POLICY_VIOLATION
from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions
from posit_bakery.plugins.builtin.wizcli.report import WizScanReportCollection
from posit_bakery.plugins.builtin.wizcli.suite import WizCLISuite
from posit_bakery.plugins.protocol import BakeryToolPlugin, ToolCallResult
from posit_bakery.settings import SETTINGS
from posit_bakery.util import auto_path

log = logging.getLogger(__name__)


class RichHelpPanelEnum(str, Enum):
    FILTERS = "Filters"
    WIZCLI = "WizCLI Options"
    AUTH = "Authentication"


class WizCLIPlugin(BakeryToolPlugin):
    name: str = "wizcli"
    description: str = "Scan container images for vulnerabilities with WizCLI"
    tool_options_class = WizCLIOptions

    def register_cli(self, app: typer.Typer) -> None:
        wizcli_app = typer.Typer(no_args_is_help=True)
        plugin = self

        @wizcli_app.command()
        @with_verbosity_flags
        def scan(
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
                    help="The image name to isolate scanning to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_version: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image version to isolate scanning to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_variant: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image variant to isolate scanning to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_os: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image OS to isolate scanning to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_platform: Annotated[
                Optional[str],
                typer.Option(
                    show_default=SETTINGS.get_host_architecture(),
                    help="Filters which image build platform to scan.",
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
                    help="Path to a build metadata file. If given, attempts to scan image artifacts in the file."
                ),
            ] = None,
            # WizCLI-specific options
            disabled_scanners: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Comma-separated scanners to disable (e.g. Vulnerability,Secret,Malware).",
                    rich_help_panel=RichHelpPanelEnum.WIZCLI,
                ),
            ] = None,
            driver: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Driver used to scan image (extract, mount, mountWithLayers).",
                    rich_help_panel=RichHelpPanelEnum.WIZCLI,
                ),
            ] = None,
            timeout: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Timeout for the scan (e.g. 1h, 30m).",
                    rich_help_panel=RichHelpPanelEnum.WIZCLI,
                ),
            ] = None,
            no_publish: Annotated[
                bool,
                typer.Option(
                    help="Disable publishing scan results to the Wiz portal.",
                    rich_help_panel=RichHelpPanelEnum.WIZCLI,
                ),
            ] = False,
            scan_context_id: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Context identifier that defines scan granularity.",
                    rich_help_panel=RichHelpPanelEnum.WIZCLI,
                ),
            ] = None,
            log_file: Annotated[
                Optional[str],
                typer.Option(
                    "--log",
                    show_default=False,
                    help="File path for wizcli debug logs.",
                    rich_help_panel=RichHelpPanelEnum.WIZCLI,
                ),
            ] = None,
            # Auth options
            client_id: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Wiz service account client ID (overrides WIZ_CLIENT_ID env var).",
                    rich_help_panel=RichHelpPanelEnum.AUTH,
                ),
            ] = None,
            client_secret: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Wiz service account client secret (overrides WIZ_CLIENT_SECRET env var).",
                    rich_help_panel=RichHelpPanelEnum.AUTH,
                ),
            ] = None,
            use_device_code: Annotated[
                bool,
                typer.Option(
                    help="Use device code flow for authentication.",
                    rich_help_panel=RichHelpPanelEnum.AUTH,
                ),
            ] = False,
            no_browser: Annotated[
                bool,
                typer.Option(
                    help="Do not open browser for device code flow.",
                    rich_help_panel=RichHelpPanelEnum.AUTH,
                ),
            ] = False,
        ) -> None:
            """Scan container images for vulnerabilities using WizCLI.

            \b
            Runs `wizcli scan container-image` against each image target in the project.
            Results are written as JSON files to the `results/wizcli/` directory.

            \b
            Images are expected to be available to the local Docker daemon. It is advised
            to run `build` before running wizcli scans.

            \b
            Requires wizcli to be installed on the system. The path to the binary can be
            set with the `WIZCLI_PATH` environment variable if not present in the system PATH.
            Authentication can be provided via `--client-id`/`--client-secret` options or
            the `WIZ_CLIENT_ID`/`WIZ_CLIENT_SECRET` environment variables.
            """
            platform = image_platform or SETTINGS.architecture
            platform = f"linux/{platform}"

            settings = BakerySettings(
                filter=BakeryConfigFilter(
                    image_name=image_name,
                    image_version=re.escape(image_version) if image_version else None,
                    image_variant=image_variant,
                    image_os=image_os,
                    image_platform=[platform],
                ),
                dev_versions=dev_versions,
                matrix_versions=matrix_versions,
            )
            c = BakeryConfig.from_context(context, settings)

            if metadata_file:
                c.load_build_metadata_from_file(metadata_file)

            results = plugin.execute(
                c.base_path,
                c.targets,
                disabled_scanners=disabled_scanners,
                driver=driver,
                client_id=client_id,
                client_secret=client_secret,
                use_device_code=use_device_code,
                no_browser=no_browser,
                timeout=timeout,
                no_publish=no_publish,
                scan_context_id=scan_context_id,
                log_file=log_file,
            )
            plugin.results(results)

        app.add_typer(wizcli_app, name="wizcli", help="Scan container images for vulnerabilities with WizCLI")

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        *,
        disabled_scanners: str | None = None,
        driver: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        use_device_code: bool = False,
        no_browser: bool = False,
        timeout: str | None = None,
        no_publish: bool = False,
        scan_context_id: str | None = None,
        log_file: str | None = None,
        **kwargs,
    ) -> list[ToolCallResult]:
        suite = WizCLISuite(
            base_path,
            targets,
            disabled_scanners=disabled_scanners,
            driver=driver,
            client_id=client_id,
            client_secret=client_secret,
            use_device_code=use_device_code,
            no_browser=no_browser,
            timeout=timeout,
            no_publish=no_publish,
            scan_context_id=scan_context_id,
            log_file=log_file,
        )
        report_collection, errors = suite.run()

        error_list = []
        if errors is not None:
            if isinstance(errors, BakeryToolRuntimeErrorGroup):
                error_list = list(errors.exceptions)
            else:
                error_list = [errors]

        results = []
        for target in targets:
            report = None
            if target.image_name in report_collection:
                target_reports = report_collection[target.image_name]
                if target.uid in target_reports:
                    _, report = target_reports[target.uid]

            target_error = None
            for err in error_list:
                if hasattr(err, "message") and str(target) in err.message:
                    target_error = err
                    break

            exit_code = 0
            if target_error is not None:
                exit_code = getattr(target_error, "exit_code", 1)
            elif report is not None and report.status_verdict != "PASS":
                # Non-zero for policy violations (exit code 4), but report was parsed
                # so this is informational — we still show the report
                pass

            artifacts = {}
            if report is not None:
                artifacts["report"] = report
            if target_error is not None:
                artifacts["execution_error"] = target_error

            results.append(
                ToolCallResult(
                    exit_code=exit_code,
                    tool_name="wizcli",
                    target=target,
                    stdout="",
                    stderr="",
                    artifacts=artifacts if artifacts else None,
                )
            )

        return results

    def results(self, results: list[ToolCallResult]) -> None:
        report_collection = WizScanReportCollection()
        has_errors = False
        has_policy_violations = False
        errors = []

        for result in results:
            if result.artifacts and "report" in result.artifacts:
                report_collection.add_report(result.target, result.artifacts["report"])
            if result.artifacts and "execution_error" in result.artifacts:
                err = result.artifacts["execution_error"]
                if getattr(err, "exit_code", 1) == WIZCLI_EXIT_CODE_POLICY_VIOLATION:
                    has_policy_violations = True
                else:
                    has_errors = True
                errors.append(err)

        if report_collection:
            stderr_console.print(report_collection.table())

        if has_policy_violations:
            stderr_console.print("-" * 80)
            stderr_console.print(
                "Security policy violation(s) detected. These issues must be addressed.",
                style="bright_red bold",
            )
            for err in errors:
                if getattr(err, "exit_code", 1) == WIZCLI_EXIT_CODE_POLICY_VIOLATION:
                    stderr_console.print(f"  {err.message}", style="error")

        if has_errors:
            stderr_console.print("-" * 80)
            for err in errors:
                if getattr(err, "exit_code", 1) != WIZCLI_EXIT_CODE_POLICY_VIOLATION:
                    stderr_console.print(err, style="error")
            stderr_console.print("❌ wizcli scan(s) failed to execute", style="error")

        if has_errors or has_policy_violations:
            raise typer.Exit(code=1)

        stderr_console.print("✅ Scans completed", style="success")
```

- [ ] **Step 2: Register entry point in pyproject.toml**

Add the wizcli entry point to `pyproject.toml` under `[project.entry-points."bakery.plugins"]`:

```toml
[project.entry-points."bakery.plugins"]
dgoss = "posit_bakery.plugins.builtin.dgoss:DGossPlugin"
oras = "posit_bakery.plugins.builtin.oras:OrasPlugin"
wizcli = "posit_bakery.plugins.builtin.wizcli:WizCLIPlugin"
```

- [ ] **Step 3: Reinstall package to register new entry point**

Run: `cd posit-bakery && uv pip install -e .`

- [ ] **Step 4: Verify CLI registration**

Run: `cd posit-bakery && uv run bakery wizcli --help`
Expected: Shows the wizcli subcommand help with `scan` listed.

Run: `cd posit-bakery && uv run bakery wizcli scan --help`
Expected: Shows all filter, wizcli, and auth options.

- [ ] **Step 5: Commit**

```bash
git add posit_bakery/plugins/builtin/wizcli/__init__.py posit_bakery/plugins/builtin/wizcli/suite.py pyproject.toml
git commit -m "feat(wizcli): add WizCLIPlugin with CLI registration and entry point"
```

---

### Task 7: Run Full Test Suite

**Files:** None (validation only)

- [ ] **Step 1: Run all unit tests**

Run: `cd posit-bakery && uv run pytest test/plugins/builtin/wizcli/ -v`
Expected: All wizcli tests PASS.

- [ ] **Step 2: Run existing tests to verify no regressions**

Run: `cd posit-bakery && uv run pytest test/ -v -k "not image_build and not slow" --ignore=test/plugins/builtin/wizcli/`
Expected: All existing tests PASS. The wizcli plugin registration via `discover_plugins()` in `test/conftest.py` should not break anything.

- [ ] **Step 3: Fix any failures and commit if needed**

If any tests fail, diagnose and fix before proceeding.