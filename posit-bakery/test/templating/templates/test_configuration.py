from pathlib import Path

import pytest

from posit_bakery.models import Config, Manifest
from posit_bakery.templating.filters import render_template
from posit_bakery.templating import TPL_MANIFEST_YAML, TPL_CONFIG_YAML

pytestmark = [
    pytest.mark.unit,
]


def test_config_template_render(tmpdir):
    """Test rendering the TPL_CONFIG_YAML template and loading it to ensure validity"""
    config_yaml = Path(tmpdir) / "config.yaml"
    with open(config_yaml, "w") as f:
        config_yaml_data = render_template(
            TPL_CONFIG_YAML,
            repo_url="github.com/rstudio/example",
        )
        f.write(config_yaml_data)
    c = Config.load(config_yaml)
    assert len(c.registries) == 1
    assert c.registries[0].host == "docker.io"
    assert c.registries[0].namespace == "posit"
    assert c.repository_url == "github.com/rstudio/example"
    assert c.vendor == "Posit Software, PBC"
    assert c.maintainer == "docker@posit.co"
    assert c.authors == []


def test_manifest_template_render(tmpdir, basic_config_obj):
    """Test rendering the TPL_MANIFEST_YAML template and loading it to ensure validity"""
    manifest_yaml = Path(tmpdir) / "manifest.yaml"
    with open(manifest_yaml, "w") as f:
        manifest_yaml_data = render_template(
            TPL_MANIFEST_YAML,
            image_name="example",
        )
        f.write(manifest_yaml_data)
    m = Manifest.load(manifest_yaml)
    assert m.image_name == "example"
