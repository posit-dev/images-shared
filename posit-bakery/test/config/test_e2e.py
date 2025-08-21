import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from posit_bakery.config import BakeryConfig
from posit_bakery.config.templating import TPL_BAKERY_CONFIG_YAML, render_template
from posit_bakery.const import DEFAULT_BASE_IMAGE
from test.helpers import IMAGE_INDENT, VERSION_INDENT

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.config,
]


def test_create_from_scratch(tmpdir):
    """Test creating a new project, image, and version from scratch."""
    context = Path(tmpdir) / "test_project"
    context.mkdir()
    repo_url = "https://github.com/posit-dev/images-shared"
    config_file = context / "bakery.yaml"

    # Create a new project.
    with patch("posit_bakery.util.try_get_repo_url") as mock_repo_url:
        mock_repo_url.return_value = repo_url
        BakeryConfig.new(context)

    # Check that the bakery.yaml file was created as expected from its template.
    assert config_file.is_file()
    expected_config = render_template(TPL_BAKERY_CONFIG_YAML, repo_url=repo_url)
    assert config_file.read_text() == expected_config

    # Load the new project
    config = BakeryConfig.from_context(context)

    # Check that the config is empty as expected.
    assert len(config.model.images) == 0

    # Create a new image.
    config.create_image("image-one")
    assert len(config.model.images) == 1
    expected_image_yaml = textwrap.indent(
        textwrap.dedent("""\
    - name: image-one
    """),
        IMAGE_INDENT,
    )
    assert expected_image_yaml in config_file.read_text()
    image_path = context / "image-one"
    assert image_path.is_dir()
    assert (image_path / "template").is_dir()
    assert (image_path / "template" / "Containerfile.ubuntu2204.jinja2").is_file()
    assert (image_path / "template" / "test").is_dir()
    assert (image_path / "template" / "test" / "goss.yaml.jinja2").is_file()
    assert (image_path / "template" / "deps").is_dir()
    assert (image_path / "template" / "deps" / "packages.txt.jinja2").is_file()

    # Create a new version for the image.
    config.create_version("image-one", "1.0.0")
    assert len(config.model.get_image("image-one").versions) == 1
    expected_version_yaml = textwrap.indent(
        textwrap.dedent("""\
    - name: 1.0.0
      latest: true
    """),
        VERSION_INDENT,
    )
    assert expected_version_yaml in config_file.read_text()
    version_path = image_path / "1.0.0"
    assert version_path.is_dir()
    assert (version_path / "Containerfile.ubuntu2204.min").is_file()
    assert (version_path / "Containerfile.ubuntu2204.std").is_file()
    expected_containerfile = f"FROM {DEFAULT_BASE_IMAGE}\n"
    assert expected_containerfile in (version_path / "Containerfile.ubuntu2204.min").read_text()
    assert expected_containerfile in (version_path / "Containerfile.ubuntu2204.std").read_text()
