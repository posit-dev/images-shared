import enum
import filecmp
import os
from pathlib import Path
from typing import List, Tuple

import pytest
import python_on_whales

from posit_bakery.config import BakeryConfig
from posit_bakery.image import ImageTarget

IMAGE_INDENT = " " * 2
VERSION_INDENT = " " * 6


class FileTestResultEnum(str, enum.Enum):
    """Enum for test result types in file tests."""

    VALID = "valid"
    VALID_WITH_WARNING = "valid-with-warning"
    INVALID = "invalid"


# Duplicate of entry in conftest.py, but required for this file
TEST_DIRECTORY = Path(os.path.dirname(os.path.realpath(__file__)))

SUCCESS_SUITES = ["basic", "barebones", "multiplatform"]
FAIL_SUITES = ["fail-fast"]


def yaml_file_testcases(test_result: FileTestResultEnum) -> List[Tuple[str, Path]]:
    """Find all YAML files in a directory for use

    Example return:
    [
        ("name1", "/path/to/name1.yaml"),
        ("name2", "/path/to/name2.yaml"),
        ("name3", "/path/to/name3.yaml"),
        ("name4", "/path/to/name4.yaml"),
    ]
    """
    directory = TEST_DIRECTORY / "testdata" / test_result
    yaml_files = directory.glob("*.yaml")

    return [pytest.param(f, id=f.stem) for f in yaml_files]


def try_format_values(value_list: List[str], **kwargs):
    return [value.format(**kwargs) for value in value_list]


def remove_images(obj: BakeryConfig | ImageTarget | None = None):
    """Remove any images created during testing."""
    if isinstance(obj, BakeryConfig):
        for target in obj.targets:
            for tag in target.tags:
                try:
                    python_on_whales.docker.image.remove(tag)
                except python_on_whales.exceptions.DockerException:
                    pass
    elif isinstance(obj, ImageTarget):
        for tag in obj.tags:
            try:
                python_on_whales.docker.image.remove(tag)
            except python_on_whales.exceptions.DockerException:
                pass
    else:
        raise ValueError("Either config_obj or target must be provided.")


def assert_directories_match(dir1, dir2):
    """Assert that files between two directories match exactly."""
    files1 = set(os.listdir(dir1))
    files2 = set(os.listdir(dir2))

    # Assert same files exist in both directories
    only_in_dir1 = files1 - files2
    only_in_dir2 = files2 - files1

    assert not only_in_dir1, f"Files only in {dir1}: {only_in_dir1}"
    assert not only_in_dir2, f"Files only in {dir2}: {only_in_dir2}"

    common_files = files1 & files2

    mismatching = []

    for filename in common_files:
        path1 = os.path.join(dir1, filename)
        path2 = os.path.join(dir2, filename)

        # Skip directories
        if os.path.isdir(path1) or os.path.isdir(path2):
            continue

        if not filecmp.cmp(path1, path2, shallow=False):
            mismatching.append(filename)

    assert not mismatching, f"Files with different content: {mismatching}"
