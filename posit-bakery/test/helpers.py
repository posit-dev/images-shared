import enum
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

SUCCESS_SUITES = ["basic", "barebones"]
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
                python_on_whales.docker.image.remove(tag)
    elif isinstance(obj, ImageTarget):
        for tag in obj.tags:
            python_on_whales.docker.image.remove(tag)
    else:
        raise ValueError("Either config_obj or target must be provided.")
