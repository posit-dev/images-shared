import enum
import filecmp
import os
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import List, Tuple
from unittest.mock import NonCallableMock, patch

import pytest
import python_on_whales

from posit_bakery.config import BakeryConfig
from posit_bakery.image import ImageTarget
from posit_bakery.targets import selection
from posit_bakery.targets.selection import select_targets

from test.helpers.registry_container import RegistryContainer

# Modules that import select_targets at module level, plus its source module for
# callers that import it at call time (imagetools).
#
# Not auto-derived: a new module that imports select_targets and is exercised by a
# CLI test with a mocked BakeryConfig must be added here by hand. Otherwise that
# test calls the real select_targets against the mock, which fails with an
# unrelated-looking error (e.g. iterating a Mock's `model.images`) rather than a
# clear "add your module to SELECT_TARGETS_MODULES" message.
SELECT_TARGETS_MODULES = (
    "posit_bakery.cli.build",
    "posit_bakery.cli.ci",
    "posit_bakery.cli.clean",
    "posit_bakery.cli.get",
    "posit_bakery.cli.run",
    "posit_bakery.plugins.builtin.dgoss",
    "posit_bakery.plugins.builtin.hadolint",
    "posit_bakery.plugins.builtin.wizcli",
    "posit_bakery.targets.selection",
)


@contextmanager
def select_targets_from_mocked_config(modules=SELECT_TARGETS_MODULES):
    """Let tests that mock BakeryConfig supply targets through ``config.targets``.

    Commands call select_targets(config, settings), which finds no images on a
    mocked config, so the command would exit with "No image targets". A mocked
    config whose test assigned ``targets`` returns that list. Everything else,
    including mocks with hand-built models, goes through the real function.
    """
    real = selection.select_targets

    def fake(config, settings, **kwargs):
        # Assigned attributes live in the instance __dict__; auto-created mock
        # children do not, so this matches only an explicit `config.targets = ...`.
        if isinstance(config, NonCallableMock) and "targets" in vars(config):
            return list(config.targets)
        return real(config, settings, **kwargs)

    with ExitStack() as stack:
        for module in modules:
            stack.enter_context(patch(f"{module}.select_targets", side_effect=fake))
        yield


IMAGE_INDENT = " " * 2
MATRIX_INDENT = " " * 4
VERSION_INDENT = " " * 6


class FileTestResultEnum(str, enum.Enum):
    """Enum for test result types in file tests."""

    VALID = "valid"
    VALID_WITH_WARNING = "valid-with-warning"
    INVALID = "invalid"


# Duplicate of entry in conftest.py, but required for this file
TEST_DIRECTORY = Path(os.path.dirname(os.path.realpath(__file__))).parent

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
        for target in select_targets(obj, obj.settings):
            for tag in target.tags.as_strings():
                try:
                    python_on_whales.docker.image.remove(tag)
                except python_on_whales.exceptions.DockerException:
                    pass
    elif isinstance(obj, ImageTarget):
        for tag in obj.tags.as_strings():
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


__all__ = [
    "FileTestResultEnum",
    "IMAGE_INDENT",
    "MATRIX_INDENT",
    "VERSION_INDENT",
    "TEST_DIRECTORY",
    "SUCCESS_SUITES",
    "FAIL_SUITES",
    "yaml_file_testcases",
    "try_format_values",
    "remove_images",
    "assert_directories_match",
    "RegistryContainer",
]
