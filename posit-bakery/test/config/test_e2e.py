import json
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


def test_create_from_scratch(tmpdir, common_image_variants):
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
    assert (image_path / "template" / "Containerfile.jinja2").is_file()
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
    assert (version_path / "Containerfile").is_file()
    expected_containerfile = f"FROM {DEFAULT_BASE_IMAGE}\n"
    assert expected_containerfile in (version_path / "Containerfile").read_text()


def test_create_from_scratch_bake_plan(tmpdir, common_image_variants_objects):
    """Test rendering a bake plan with a new project, image, and version from scratch."""
    context = Path(tmpdir) / "test_project"
    context.mkdir()
    repo_url = "https://github.com/posit-dev/images-shared"

    # Create a new project.
    with patch("posit_bakery.util.try_get_repo_url") as mock_repo_url:
        mock_repo_url.return_value = repo_url
        BakeryConfig.new(context)

    # Load the new project
    config = BakeryConfig.from_context(context)

    # Create a new image.
    config.create_image("image-one")
    # Add the Standard and Minimal Variants to the image.
    config.model.images[0].variants = common_image_variants_objects

    # Create a second empty image to ensure it does not render without versions.
    config.create_image("image-two")

    # Create a new version for the image.
    config.create_version("image-one", "1.0.0")

    # Regenerate targets.
    config.generate_image_targets()

    # Render the bake plan.
    result = config.bake_plan_targets()

    expected_plan = {
        "group": {
            "default": {
                "targets": ["image-one-1-0-0-minimal", "image-one-1-0-0-standard"],
            },
            "image-one": {
                "targets": ["image-one-1-0-0-minimal", "image-one-1-0-0-standard"],
            },
            "Minimal": {
                "targets": ["image-one-1-0-0-minimal"],
            },
            "Standard": {
                "targets": ["image-one-1-0-0-standard"],
            },
        },
        "target": {
            "image-one-1-0-0-minimal": {
                "context": ".",
                "dockerfile": "image-one/1.0.0/Containerfile.min",
                "labels": {
                    "org.opencontainers.image.created": "2025-01-01T00:00:00",
                    "org.opencontainers.image.source": "https://github.com/posit-dev/images-shared",
                    "org.opencontainers.image.title": "Image One",
                    "org.opencontainers.image.vendor": "Posit Software, PBC",
                    "co.posit.image.maintainer": "Posit Docker Team <docker@posit.co>",
                    "co.posit.image.name": "Image One",
                    "org.opencontainers.image.version": "1.0.0",
                    "org.opencontainers.image.revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "co.posit.image.version": "1.0.0",
                    "co.posit.image.revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "co.posit.image.variant": "Minimal",
                },
                "tags": [
                    "docker.io/posit/image-one:1.0.0-min",
                    "docker.io/posit/image-one:min",
                ],
                "platforms": ["linux/amd64"],
            },
            "image-one-1-0-0-standard": {
                "context": ".",
                "dockerfile": "image-one/1.0.0/Containerfile.std",
                "labels": {
                    "org.opencontainers.image.created": "2025-01-01T00:00:00",
                    "org.opencontainers.image.source": "https://github.com/posit-dev/images-shared",
                    "org.opencontainers.image.title": "Image One",
                    "org.opencontainers.image.vendor": "Posit Software, PBC",
                    "co.posit.image.maintainer": "Posit Docker Team <docker@posit.co>",
                    "co.posit.image.name": "Image One",
                    "org.opencontainers.image.version": "1.0.0",
                    "org.opencontainers.image.revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "co.posit.image.version": "1.0.0",
                    "co.posit.image.revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "co.posit.image.variant": "Standard",
                },
                "tags": [
                    "docker.io/posit/image-one:1.0.0",
                    "docker.io/posit/image-one:1.0.0-std",
                    "docker.io/posit/image-one:latest",
                    "docker.io/posit/image-one:std",
                ],
                "platforms": ["linux/amd64"],
            },
        },
    }

    assert result == json.dumps(expected_plan, indent=2)
