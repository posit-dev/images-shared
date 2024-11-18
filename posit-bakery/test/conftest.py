import os
import shutil
from pathlib import Path

import pytest
import tomlkit

TEST_DIRECTORY = Path(os.path.dirname(os.path.realpath(__file__)))


@pytest.fixture
def toml_basic_str():
    """Return a basic TOML document as a string"""
    return """name = "basic"

[section]
key = "value"
"""


@pytest.fixture
def toml_basic_file(tmp_path, toml_basic_str):
    """Return a basic TOML document as a filepath"""
    filepath = tmp_path / "basic.toml"
    with open(filepath, "w") as f:
        f.write(toml_basic_str)
    return filepath


@pytest.fixture(scope="session")
def resource_path():
    """Return the path to the test resources directory"""
    return TEST_DIRECTORY / "resources"


@pytest.fixture(scope="session")
def basic_context(resource_path):
    """Return the path to the basic test suite context"""
    return resource_path / "basic"


@pytest.fixture(scope="session")
def basic_config_file(basic_context):
    """Return the path to the basic test suite config.toml file"""
    return basic_context / "config.toml"


@pytest.fixture
def basic_config_obj(basic_config_file):
    """Return a Config object loaded from basic test suite config.toml file"""
    from posit_bakery.models.config import Config
    return Config.load_file(basic_config_file)


@pytest.fixture
def basic_manifest_file(basic_context):
    """Return the path to the basic test suite manifest.toml file"""
    return basic_context / "test-image" / "manifest.toml"


@pytest.fixture
def basic_manifest_obj(basic_config_obj, basic_manifest_file):
    """Return a Manifest object loaded from basic test suite manifest.toml file"""
    from posit_bakery.models.manifest import Manifest
    return Manifest.load_file_with_config(basic_config_obj, basic_manifest_file)


@pytest.fixture
def basic_manifest_types(basic_manifest_file):
    """Return the target types in the basic manifest.toml file"""
    with open(basic_manifest_file, 'rb') as f:
        d = tomlkit.load(f)
    return d["target"].keys()


@pytest.fixture
def basic_manifest_versions(basic_manifest_file):
    """Return the target types in the basic manifest.toml file"""
    with open(basic_manifest_file, 'rb') as f:
        d = tomlkit.load(f)
    return d["build"].keys()


@pytest.fixture
def basic_manifest_os_plus_versions(basic_manifest_file):
    """Return the versions/os pairs in the basic manifest.toml file"""
    results = []
    with open(basic_manifest_file, 'rb') as f:
        d = tomlkit.load(f)
    for version, data in d["build"].items():
        if "os" in data and type(data["os"]) is list:
            for _os in data["os"]:
                results.append((version, _os))
        elif "os" in d.get("const", {}):
            if type(d["const"]["os"]) is list:
                for _os in d["const"]["os"]:
                    results.append((version, _os))
            else:
                results.append((version, d["const"]["os"]))
        else:
            results.append((version,))
    return results


@pytest.fixture
def basic_expected_num_target_builds(basic_manifest_types, basic_manifest_os_plus_versions):
    """Returns the expected number of target builds for the basic manifest.toml"""
    return len(basic_manifest_types) * len(basic_manifest_os_plus_versions)


@pytest.fixture
def basic_tmpcontext(tmpdir, basic_context):
    """Return a temporary copy of the basic test suite context"""
    tmpcontext = Path(tmpdir) / "basic"
    tmpcontext.mkdir(parents=True, exist_ok=True)
    shutil.copytree(basic_context, tmpcontext, dirs_exist_ok=True)
    return tmpcontext
