from pathlib import Path

import pytest

from posit_bakery.models.config import Config
from posit_bakery.models.manifest import Manifest
from posit_bakery.templating.filters import render_template
from posit_bakery.templating.templates import configuration

pytestmark = [
    pytest.mark.unit,
]


def test_config_template_render(tmpdir):
    """Test rendering the TPL_CONFIG_TOML template and loading it to ensure validity"""
    config_toml = Path(tmpdir) / "config.toml"
    with open(config_toml, "w") as f:
        config_toml_data = render_template(
            configuration.TPL_CONFIG_TOML,
            repo_url="github.com/rstudio/example",
        )
        f.write(config_toml_data)
    c = Config.load(config_toml)
    assert len(c.registries) == 1
    assert c.registries[0].host == "docker.io"
    assert c.registries[0].namespace == "posit"
    assert c.repository_url == "github.com/rstudio/example"
    assert c.vendor == "Posit Software, PBC"
    assert c.maintainer == "docker@posit.co"
    assert c.authors == []


def test_manifest_template_render(tmpdir, basic_config_obj):
    """Test rendering the TPL_MANIFEST_TOML template and loading it to ensure validity"""
    manifest_toml = Path(tmpdir) / "manifest.toml"
    with open(manifest_toml, "w") as f:
        manifest_toml_data = render_template(
            configuration.TPL_MANIFEST_TOML,
            image_name="example",
        )
        f.write(manifest_toml_data)
    m = Manifest.load(basic_config_obj, manifest_toml)
    assert m.image_name == "example"
