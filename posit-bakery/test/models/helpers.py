import os
import textwrap
from pathlib import Path
from typing import List, Tuple

import pytest
import tomlkit

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
