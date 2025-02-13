import os
import textwrap
from pathlib import Path
from typing import List, Tuple
from unittest.mock import MagicMock

import pytest
import tomlkit

from posit_bakery.models import Manifest, Config
from posit_bakery.models.manifest.snyk import ManifestSnyk, ManifestSnykTest, \
    ManifestSnykTestOutput, ManifestSnykMonitor, ManifestSnykSbom, SnykSeverityThresholdEnum, SnykSbomFormatEnum, \
    SNYK_DEFAULT_SEVERITY_THRESHOLD, SNYK_DEFAULT_SBOM_FORMAT

# Duplicate of entry in conftest.py, but required for this file
TEST_DIRECTORY = Path(os.path.dirname(os.path.realpath(__file__))).parent


def dedent_toml(toml_str: str) -> tomlkit.TOMLDocument:
    toml_str = textwrap.dedent(toml_str)

    return tomlkit.parse(toml_str)


def toml_file_testcases(schema_type: str, test_result: str) -> List[Tuple[str, Path]]:
    """Find all TOML files in a directory for use

    Example return:
    [
        ("name1", "/path/to/name1.toml"),
        ("name2", "/path/to/name2.toml"),
        ("name3", "/path/to/name3.toml"),
        ("name4", "/path/to/name4.toml"),
    ]
    """
    directory = TEST_DIRECTORY / "testdata" / schema_type / test_result
    toml_files = directory.glob("*.toml")

    return [pytest.param(f, id=f.stem) for f in toml_files]


def try_format_values(value_list: List[str], **kwargs):
    return [value.format(**kwargs) for value in value_list]


def snyk_test_argument_testcases() -> List[pytest.mark.ParameterSet]:
    return [
        pytest.param(
            ManifestSnyk(),
            [
                "--severity-threshold",
                SNYK_DEFAULT_SEVERITY_THRESHOLD.value,
                "--app-vulns",
                "--exclude-base-image-vulns",
            ],
            id="default",
        ),
        pytest.param(
            ManifestSnyk(test=ManifestSnykTest(severity_threshold="high")),
            ["--severity-threshold", "high", "--app-vulns", "--exclude-base-image-vulns"],
            id="override_severity_threshold",
        ),
        pytest.param(
            ManifestSnyk(test=ManifestSnykTest(include_app_vulns=False)),
            [
                "--severity-threshold",
                SNYK_DEFAULT_SEVERITY_THRESHOLD.value,
                "--exclude-app-vulns",
                "--exclude-base-image-vulns",
            ],
            id="exclude_app_vulns",
        ),
        pytest.param(
            ManifestSnyk(test=ManifestSnykTest(include_base_image_vulns=True)),
            ["--severity-threshold", SNYK_DEFAULT_SEVERITY_THRESHOLD.value, "--app-vulns"],
            id="include_base_image_vulns",
        ),
        pytest.param(
            ManifestSnyk(test=ManifestSnykTest(include_node_modules=False)),
            [
                "--severity-threshold",
                SNYK_DEFAULT_SEVERITY_THRESHOLD.value,
                "--app-vulns",
                "--exclude-base-image-vulns",
                "--exclude-node-modules",
            ],
            id="exclude_node_modules",
        ),
        pytest.param(
            ManifestSnyk(test=ManifestSnykTest(output=ManifestSnykTestOutput(format="json"))),
            [
                "--json",
                "--severity-threshold",
                SNYK_DEFAULT_SEVERITY_THRESHOLD.value,
                "--app-vulns",
                "--exclude-base-image-vulns",
            ],
            id="output_json",
        ),
        pytest.param(
            ManifestSnyk(test=ManifestSnykTest(output=ManifestSnykTestOutput(format="sarif"))),
            [
                "--sarif",
                "--severity-threshold",
                SNYK_DEFAULT_SEVERITY_THRESHOLD.value,
                "--app-vulns",
                "--exclude-base-image-vulns",
            ],
            id="output_sarif",
        ),
        pytest.param(
            ManifestSnyk(test=ManifestSnykTest(output=ManifestSnykTestOutput(json_file=True))),
            [
                "--json-file-output",
                "{context}/snyk_test/{uid}.json",
                "--severity-threshold",
                SNYK_DEFAULT_SEVERITY_THRESHOLD.value,
                "--app-vulns",
                "--exclude-base-image-vulns",
            ],
            id="output_json_file",
        ),
        pytest.param(
            ManifestSnyk(test=ManifestSnykTest(output=ManifestSnykTestOutput(sarif_file=True))),
            [
                "--sarif-file-output",
                "{context}/snyk_test/{uid}.sarif",
                "--severity-threshold",
                SNYK_DEFAULT_SEVERITY_THRESHOLD.value,
                "--app-vulns",
                "--exclude-base-image-vulns",
            ],
            id="output_sarif_file",
        ),
    ]


def snyk_monitor_argument_testcases() -> List[pytest.mark.ParameterSet]:
    return [
        pytest.param(
            ManifestSnyk(),
            [],
            id="default",
        ),
        pytest.param(
            ManifestSnyk(monitor=ManifestSnykMonitor(output_json=True)),
            ["--json"],
            id="output_json",
        ),
        pytest.param(
            ManifestSnyk(monitor=ManifestSnykMonitor(environment="internal")),
            ["--project-environment", "internal"],
            id="environment_single",
        ),
        pytest.param(
            ManifestSnyk(monitor=ManifestSnykMonitor(environment=["internal", "distributed", "saas"])),
            ["--project-environment", "internal,distributed,saas"],
            id="environment_multi",
        ),
        pytest.param(
            ManifestSnyk(monitor=ManifestSnykMonitor(lifecycle="development")),
            ["--project-lifecycle", "development"],
            id="lifecycle_single",
        ),
        pytest.param(
            ManifestSnyk(monitor=ManifestSnykMonitor(lifecycle=["development", "sandbox"])),
            ["--project-lifecycle", "development,sandbox"],
            id="lifecycle_multi",
        ),
        pytest.param(
            ManifestSnyk(monitor=ManifestSnykMonitor(business_criticality="low")),
            ["--project-business-criticality", "low"],
            id="business_criticality_single",
        ),
        pytest.param(
            ManifestSnyk(monitor=ManifestSnykMonitor(business_criticality=["low", "medium", "high"])),
            ["--project-business-criticality", "low,medium,high"],
            id="business_criticality_multi",
        ),
        pytest.param(
            ManifestSnyk(monitor=ManifestSnykMonitor(tags={"key1": "value1"})),
            ["--project-tags", "'key1=value1'"],
            id="project_tags_single",
        ),
        pytest.param(
            ManifestSnyk(monitor=ManifestSnykMonitor(tags={"key1": "value1", "key2": "value2"})),
            ["--project-tags", "'key1=value1,key2=value2'"],
            id="project_tags_multi",
        ),
        pytest.param(
            ManifestSnyk(monitor=ManifestSnykMonitor(include_node_modules=False)),
            ["--exclude-node-modules"],
            id="exclude_node_modules",
        ),
    ]


def snyk_sbom_argument_testcases() -> List[pytest.mark.ParameterSet]:
    return [
        pytest.param(
            ManifestSnyk(),
            ["--format", SNYK_DEFAULT_SBOM_FORMAT.value],
            id="default",
        ),
        pytest.param(
            ManifestSnyk(sbom=ManifestSnykSbom(format="cyclonedx1.4+xml")),
            ["--format", "cyclonedx1.4+xml"],
            id="alternate_format",
        ),
        pytest.param(
            ManifestSnyk(sbom=ManifestSnykSbom(include_app_vulns=False)),
            ["--format", SNYK_DEFAULT_SBOM_FORMAT.value, "--exclude-app-vulns"],
            id="exclude_app_vulns",
        ),
    ]


def snyk_all_argument_testcases() -> List[pytest.mark.ParmeterSet]:
    testcases = []
    for test in snyk_test_argument_testcases():
        snyk_config, expected = test.values
        expected = [
            "snyk",
            "container",
            "test",
            "--project-name",
            "{variant.meta.name}",
            "--file",
            "{variant.containerfile}",
            *expected,
        ]
        testcases.append(
            pytest.param(
                "test",
                snyk_config,
                expected,
                id=f"SnykContainerTest_{test.id}",
            )
        )
    for test in snyk_monitor_argument_testcases():
        snyk_config, expected = test.values
        expected = [
            "snyk",
            "container",
            "monitor",
            "--project-name",
            "{variant.meta.name}",
            "--file",
            "{variant.containerfile}",
            *expected,
        ]
        testcases.append(
            pytest.param(
                "monitor",
                snyk_config,
                expected,
                id=f"SnykContainerMonitor_{test.id}",
            )
        )
    for test in snyk_sbom_argument_testcases():
        snyk_config, expected = test.values
        expected = [
            "snyk",
            "container",
            "sbom",
            *expected,
        ]
        testcases.append(
            pytest.param(
                "sbom",
                snyk_config,
                expected,
                id=f"SnykContainerSbom_{test.id}",
            )
        )
    return testcases
