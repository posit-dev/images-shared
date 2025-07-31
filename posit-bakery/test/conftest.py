import os
import shutil
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from posit_bakery.config.config import BakeryConfig

TEST_DIRECTORY = Path(os.path.dirname(os.path.realpath(__file__)))


@pytest.fixture
def yaml_basic_str():
    """Return a basic YAML document as a string"""
    return """name: "basic"

section:
  key: "value"
"""


@pytest.fixture
def yaml_basic_file(tmp_path, yaml_basic_str):
    """Return a basic YAML document as a filepath"""
    filepath = tmp_path / "basic.yaml"
    with open(filepath, "w") as f:
        f.write(yaml_basic_str)
    return filepath


@pytest.fixture(scope="session")
def resource_path():
    """Return the path to the test resources directory"""
    return TEST_DIRECTORY / "resources"


@pytest.fixture(scope="session")
def testdata_path():
    """Return the path to the test data directory"""
    return TEST_DIRECTORY / "testdata"


@pytest.fixture(scope="session")
def basic_context(resource_path):
    """Return the path to the basic test suite context"""
    return resource_path / "multi-config" / "basic"


@pytest.fixture(scope="session")
def basic_unified_config_context(resource_path):
    """Return the path to the basic test suite context"""
    return resource_path / "unified-config" / "basic"


@pytest.fixture(scope="session")
def basic_config_file(basic_context):
    """Return the path to the basic test suite config.yaml file"""
    return basic_context / "config.yaml"


@pytest.fixture(scope="session")
def basic_unified_config_file(basic_unified_config_context):
    """Return the path to the basic test suite unified config.yaml file"""
    return basic_unified_config_context / "bakery.yaml"


@pytest.fixture
def basic_config_obj(basic_config_file):
    """Return a Config object loaded from basic test suite config.yaml file"""
    from posit_bakery.models import Config

    return Config.load(basic_config_file)


@pytest.fixture
def basic_unified_config_obj(basic_unified_config_file):
    """Return a Config object loaded from basic test suite unified config.yaml file"""
    return BakeryConfig(basic_unified_config_file)


@pytest.fixture
def basic_manifest_file(basic_context):
    """Return the path to the basic test suite manifest.yaml file"""
    return basic_context / "test-image" / "manifest.yaml"


@pytest.fixture
def basic_manifest_obj(basic_manifest_file):
    """Return a Manifest object loaded from basic test suite manifest.yaml file"""
    from posit_bakery.models import Manifest

    return Manifest.load(basic_manifest_file)


@pytest.fixture
def basic_manifest_types(basic_manifest_file):
    """Return the target types in the basic manifest.yaml file"""
    y = YAML()
    d = y.load(Path(basic_manifest_file))
    return d["target"].keys()


@pytest.fixture
def basic_manifest_versions(basic_manifest_file):
    """Return the target types in the basic manifest.yaml file"""
    y = YAML()
    d = y.load(Path(basic_manifest_file))
    return d["build"].keys()


@pytest.fixture
def basic_manifest_os_plus_versions(basic_manifest_file):
    """Return the versions/os pairs in the basic manifest.yaml file"""
    results = []
    y = YAML()
    d = y.load(Path(basic_manifest_file))
    for version, data in d["build"].items():
        if "os" in data and isinstance(data["os"], list):
            for _os in data["os"]:
                results.append((version, _os))
        elif "os" in d.get("const", {}):
            if isinstance(d["const"]["os"], list):
                for _os in d["const"]["os"]:
                    results.append((version, _os))
            else:
                results.append((version, d["const"]["os"]))
        else:
            results.append((version,))
    return results


@pytest.fixture
def basic_images_obj(basic_config_obj, basic_manifest_obj):
    """Return a dict of images loaded from the basic test suite manifest.yaml file"""
    from posit_bakery.models import Images

    return Images.load(config=basic_config_obj, manifests={basic_manifest_obj.image_name: basic_manifest_obj})


@pytest.fixture
def basic_expected_num_variants(basic_manifest_types, basic_manifest_os_plus_versions):
    """Returns the expected number of target builds for the basic manifest.yaml"""
    return len(basic_manifest_types) * len(basic_manifest_os_plus_versions)


@pytest.fixture
def basic_tmpcontext(tmpdir, basic_context):
    """Return a temporary copy of the basic test suite context"""
    tmpcontext = Path(tmpdir) / "basic"
    tmpcontext.mkdir(parents=True, exist_ok=True)
    shutil.copytree(basic_context, tmpcontext, dirs_exist_ok=True)
    return tmpcontext


@pytest.fixture
def basic_unified_tmpcontext(tmpdir, basic_unified_config_context):
    """Return a temporary copy of the basic unified test suite context"""
    tmpcontext = Path(tmpdir) / "basic"
    tmpcontext.mkdir(parents=True, exist_ok=True)
    shutil.copytree(basic_unified_config_context, tmpcontext, dirs_exist_ok=True)
    return tmpcontext


@pytest.fixture(scope="session")
def barebones_context(resource_path):
    """Return the path to the basic test suite context"""
    return resource_path / "multi-config" / "barebones"


@pytest.fixture(scope="session")
def barebones_unified_context(resource_path):
    """Return the path to the basic test suite unified context"""
    return resource_path / "unified-config" / "barebones"


@pytest.fixture(scope="session")
def barebones_config_file(barebones_context):
    """Return the path to the basic test suite config.yaml file"""
    return barebones_context / "config.yaml"


@pytest.fixture(scope="session")
def barebones_unified_config_file(barebones_unified_context):
    """Return the path to the basic test suite unified config.yaml file"""
    return barebones_unified_context / "bakery.yaml"


@pytest.fixture
def barebones_config_obj(barebones_config_file):
    """Return a Config object loaded from basic test suite config.yaml file"""
    from posit_bakery.models import Config

    return Config.load(barebones_config_file)


@pytest.fixture
def barebones_unified_config_obj(barebones_unified_config_file):
    """Return a Config object loaded from basic test suite unified config.yaml file"""
    return BakeryConfig(barebones_unified_config_file)


@pytest.fixture
def barebones_manifest_file(barebones_context):
    """Return the path to the basic test suite manifest.yaml file"""
    return barebones_context / "test-image" / "manifest.yaml"


@pytest.fixture
def barebones_manifest_obj(barebones_manifest_file):
    """Return a Manifest object loaded from basic test suite manifest.yaml file"""
    from posit_bakery.models import Manifest

    return Manifest.load(barebones_manifest_file)


@pytest.fixture
def barebones_manifest_types(barebones_manifest_file):
    """Return the target types in the basic manifest.yaml file"""
    y = YAML()
    d = y.load(Path(barebones_manifest_file))
    return d["target"].keys()


@pytest.fixture
def barebones_manifest_versions(barebones_manifest_file):
    """Return the target types in the basic manifest.yaml file"""
    y = YAML()
    d = y.load(Path(barebones_manifest_file))
    return d["build"].keys()


@pytest.fixture
def barebones_manifest_os_plus_versions(barebones_manifest_file):
    """Return the versions/os pairs in the basic manifest.yaml file"""
    results = []
    y = YAML()
    d = y.load(Path(barebones_manifest_file))
    for version, data in d["build"].items():
        if "os" in data and isinstance(data["os"], list):
            for _os in data["os"]:
                results.append((version, _os))
        elif "os" in d.get("const", {}):
            if isinstance(d["const"]["os"], list):
                for _os in d["const"]["os"]:
                    results.append((version, _os))
            else:
                results.append((version, d["const"]["os"]))
        else:
            results.append((version,))
    return results


@pytest.fixture
def barebones_images_obj(barebones_config_obj, barebones_manifest_obj):
    """Return a dict of images loaded from the basic test suite manifest.yaml file"""
    from posit_bakery.models import Images

    return Images.load(
        config=barebones_config_obj, manifests={barebones_manifest_obj.image_name: barebones_manifest_obj}
    )


@pytest.fixture
def barebones_expected_num_variants(barebones_manifest_types, barebones_manifest_os_plus_versions):
    """Returns the expected number of target builds for the basic manifest.yaml"""
    return len(barebones_manifest_types) * len(barebones_manifest_os_plus_versions)


@pytest.fixture
def barebones_tmpcontext(tmpdir, barebones_context):
    """Return a temporary copy of the basic test suite context"""
    tmpcontext = Path(tmpdir) / "basic"
    tmpcontext.mkdir(parents=True, exist_ok=True)
    shutil.copytree(barebones_context, tmpcontext, dirs_exist_ok=True)
    return tmpcontext


@pytest.fixture
def barebones_unified_tmpcontext(tmpdir, barebones_unified_context):
    """Return a temporary copy of the basic unified test suite context"""
    tmpcontext = Path(tmpdir) / "barebones"
    tmpcontext.mkdir(parents=True, exist_ok=True)
    shutil.copytree(barebones_unified_context, tmpcontext, dirs_exist_ok=True)
    return tmpcontext
