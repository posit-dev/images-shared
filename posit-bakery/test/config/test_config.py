import os
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from posit_bakery.config.config import BakeryConfigDocument, BakeryConfig, BakeryConfigFilter
from test.helpers import yaml_file_testcases, FileTestResultEnum

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]

IMAGE_INDENT = " " * 2
VERSION_INDENT = " " * 6


class TestBakeryConfigDocument:
    def test_required_fields(self):
        """Test that a BakeryConfigDocument can be created with only the required fields."""
        base_path = Path(os.getcwd())
        d = BakeryConfigDocument(base_path=base_path, repository={"url": "https://example.com/repo"})
        assert d.base_path == base_path
        assert d.path == base_path
        assert str(d.repository.url) == "https://example.com/repo"
        assert len(d.registries) == 0
        assert len(d.images) == 0

    def test_valid(self):
        """Test creating a valid BakeryConfigDocument with all fields."""
        base_path = Path(os.getcwd())
        d = BakeryConfigDocument(
            base_path=base_path,
            repository={"url": "https://example.com/repo"},
            registries=[{"host": "registry.example.com", "namespace": "namespace"}],
            images=[{"name": "my-image", "versions": [{"name": "1.0.0"}]}],
        )

        assert d.base_path == base_path
        assert str(d.repository.url) == "https://example.com/repo"
        assert len(d.registries) == 1
        assert d.registries[0].host == "registry.example.com"
        assert d.registries[0].namespace == "namespace"
        assert len(d.images) == 1
        assert d.images[0].name == "my-image"
        assert len(d.images[0].versions) == 1
        assert d.images[0].versions[0].name == "1.0.0"
        assert len(d.images[0].variants) == 2
        assert d.images[0].variants[0].name == "Standard"
        assert d.images[0].variants[1].name == "Minimal"

    def test_deduplicate_registries(self, caplog):
        """Test that duplicate registries are deduplicated."""
        base_path = Path(os.getcwd())
        d = BakeryConfigDocument(
            base_path=base_path,
            repository={"url": "https://example.com/repo"},
            registries=[
                {"host": "registry.example.com", "namespace": "namespace"},
                {"host": "registry.example.com", "namespace": "namespace"},  # Duplicate
            ],
        )
        assert len(d.registries) == 1
        assert d.registries[0].host == "registry.example.com"
        assert d.registries[0].namespace == "namespace"
        assert "WARNING" in caplog.text
        assert "Duplicate registry defined in config: registry.example.com/namespace" in caplog.text

    def test_check_images_not_empty(self, caplog):
        """Test that a warning is logged if no images are defined."""
        base_path = Path(os.getcwd())
        d = BakeryConfigDocument(base_path=base_path, repository={"url": "https://example.com/repo"})
        assert len(d.images) == 0
        assert "WARNING" in caplog.text
        assert "No images found in the Bakery config. At least one image is required for most commands." in caplog.text

    def test_check_image_duplicates(self):
        """Test that an error is raised if duplicate image names are found."""
        base_path = Path(os.getcwd())
        with pytest.raises(ValueError, match="Duplicate image names found in the bakery config:"):
            BakeryConfigDocument(
                base_path=base_path,
                repository={"url": "https://example.com/repo"},
                images=[
                    {"name": "my-image"},
                    {"name": "my-image"},  # Duplicate
                ],
            )

    def test_resolve_parentage(self):
        """Test that the parent field is set correctly."""
        base_path = Path(os.getcwd())
        d = BakeryConfigDocument(
            base_path=base_path,
            repository={"url": "https://example.com/repo"},
            images=[{"name": "my-image"}],
        )
        assert d.images[0].parent is d
        assert d.repository.parent is d

    def test_path(self):
        """Test that the path property returns the base path."""
        base_path = Path(os.getcwd())
        d = BakeryConfigDocument(base_path=base_path, repository={"url": "https://example.com/repo"})
        assert d.path == base_path

    def test_get_image(self):
        """Test that get_image returns the correct image."""
        base_path = Path(os.getcwd())
        d = BakeryConfigDocument(
            base_path=base_path,
            repository={"url": "https://example.com/repo"},
            images=[{"name": "my-image"}],
        )
        image = d.get_image("my-image")
        assert image is not None
        assert image.name == "my-image"

        # Test for a non-existent image
        assert d.get_image("non-existent") is None

    def test_create_image_files_template(self, basic_tmpcontext):
        """Test that create_image_files_template creates the correct directory structure."""
        assert not (basic_tmpcontext / "new-image").is_dir()
        d = BakeryConfigDocument(base_path=basic_tmpcontext, repository={"url": "https://example.com/repo"})
        d.create_image_files_template(basic_tmpcontext / "new-image", "new-image", "ubuntu:22.04")
        assert (basic_tmpcontext / "new-image").is_dir()
        assert (basic_tmpcontext / "new-image" / "template" / "Containerfile.ubuntu2204.jinja2").exists()
        assert (basic_tmpcontext / "new-image" / "template" / "deps").is_dir()
        assert (basic_tmpcontext / "new-image" / "template" / "deps" / "packages.txt.jinja2").is_file()
        assert (basic_tmpcontext / "new-image" / "template" / "test").is_dir()
        assert (basic_tmpcontext / "new-image" / "template" / "test" / "goss.yaml.jinja2").is_file()

    def test_create_image_model(self):
        """Test that create_image adds a new image to the config."""
        base_path = Path(os.getcwd())
        d = BakeryConfigDocument(base_path=base_path, repository={"url": "https://example.com/repo"})
        new_image = d.create_image_model("new-image")
        assert new_image.name == "new-image"
        assert len(d.images) == 1
        assert d.images[0] is new_image
        assert new_image.parent is d


class TestBakeryConfig:
    @pytest.mark.parametrize("yaml_file", yaml_file_testcases(FileTestResultEnum.VALID))
    def test_valid(self, caplog, yaml_file: Path):
        """Test valid YAML config files

        Files are stored in test/testdata/valid
        """
        config = BakeryConfig(yaml_file)
        assert config is not None
        assert "WARNING" not in caplog.text

    @pytest.mark.parametrize("yaml_file", yaml_file_testcases(FileTestResultEnum.VALID_WITH_WARNING))
    def test_valid_with_warning(self, caplog, yaml_file: Path):
        """Test valid YAML config files with warnings

        Files are stored in test/testdata/valid-with-warning
        """
        config = BakeryConfig(yaml_file)
        assert config is not None
        assert "WARNING" in caplog.text

    @pytest.mark.parametrize("yaml_file", yaml_file_testcases(FileTestResultEnum.INVALID))
    def test_invalid(self, yaml_file: Path):
        """Test invalid YAML config files

        Files are stored in test/testdata/invalid
        """
        with pytest.raises(ValidationError):
            BakeryConfig(yaml_file)

    def test_config_does_not_exist(self):
        """Test that a FileNotFoundError is raised if the config file does not exist."""
        with pytest.raises(FileNotFoundError, match="File '.*' does not exist."):
            BakeryConfig("non_existent_config.yaml")

    def test_new(self, tmpdir):
        """Test creating a new BakeryConfig creates a valid bakery.yaml in a given directory."""
        with patch("posit_bakery.util.try_get_repo_url") as mock_repo_url:
            mock_repo_url.return_value = "https://example.com/repo"
            BakeryConfig.new(Path(tmpdir))

        assert (Path(tmpdir) / "bakery.yaml").is_file()
        BakeryConfig(Path(tmpdir) / "bakery.yaml")

    def test_create_image_image_exists(self, barebones_tmpcontext):
        """Test creating a new image in the BakeryConfig."""
        config = BakeryConfig.from_context(barebones_tmpcontext)
        with pytest.raises(ValueError, match="Image 'scratch' already exists"):
            config.create_image("scratch")

    def test_create_image(self, barebones_tmpcontext):
        """Test creating a new image in the BakeryConfig."""
        config = BakeryConfig.from_context(barebones_tmpcontext)
        assert len(config.model.images) == 1
        config.create_image(
            "new-image",
        )
        assert len(config.model.images) == 2
        expected_yaml = textwrap.indent(
            textwrap.dedent("""\
          - name: new-image
        """),
            IMAGE_INDENT,
        )
        assert expected_yaml in (barebones_tmpcontext / "bakery.yaml").read_text()
        assert (barebones_tmpcontext / "new-image").is_dir()
        assert (barebones_tmpcontext / "new-image" / "template").is_dir()
        assert (barebones_tmpcontext / "new-image" / "template" / "Containerfile.ubuntu2204.jinja2").is_file()

    def test_create_image_customized(self, barebones_tmpcontext):
        """Test creating a new image in the BakeryConfig."""
        config = BakeryConfig.from_context(barebones_tmpcontext)
        assert len(config.model.images) == 1
        config.create_image(
            "new-image",
            base_image="docker.io/library/ubuntu:24.04",
            subpath="image",
            display_name="Cool New Image",
            description="This is a new image for testing purposes.",
            documentation_url="https://example.com/docs/new-image",
        )
        assert len(config.model.images) == 2
        expected_yaml = textwrap.indent(
            textwrap.dedent("""\
          - name: new-image
            displayName: Cool New Image
            description: This is a new image for testing purposes.
            documentationUrl: https://example.com/docs/new-image
            subpath: image
        """),
            IMAGE_INDENT,
        )
        assert expected_yaml in (barebones_tmpcontext / "bakery.yaml").read_text()
        assert (barebones_tmpcontext / "image").is_dir()
        assert (barebones_tmpcontext / "image" / "template").is_dir()
        assert (barebones_tmpcontext / "image" / "template" / "Containerfile.ubuntu2404.jinja2").is_file()
        assert (
            "FROM docker.io/library/ubuntu:24.04"
            in (barebones_tmpcontext / "image" / "template" / "Containerfile.ubuntu2404.jinja2").read_text()
        )

    def test_create_version_exists(self, barebones_tmpcontext):
        """Test creating an existing version in the BakeryConfig generates an error."""
        config = BakeryConfig.from_context(barebones_tmpcontext)

        with pytest.raises(ValueError, match="Version '1.0.0' already exists for image 'scratch'"):
            config.create_version("scratch", "1.0.0")

    def test_create_version(self, barebones_tmpcontext):
        """Test creating a new version in the BakeryConfig."""
        config = BakeryConfig.from_context(barebones_tmpcontext)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert len(image.versions) == 1

        config.create_version("scratch", "2.0.0")
        assert len(config.model.images) == 1
        assert len(image.versions) == 2
        expected_yaml = textwrap.indent(
            textwrap.dedent("""\
              - name: 2.0.0
                latest: true
                os:
                  - name: Scratch
                    primary: true
        """),
            VERSION_INDENT,
        )
        assert expected_yaml in (barebones_tmpcontext / "bakery.yaml").read_text()
        assert (barebones_tmpcontext / "scratch" / "2.0.0").is_dir()
        assert (barebones_tmpcontext / "scratch" / "2.0.0" / "Containerfile.scratch.min").is_file()
        expected_containerfile = textwrap.dedent("""\
        FROM scratch

        COPY scratch/2.0.0/deps/packages.txt /tmp/packages.txt
        """)
        assert (
            expected_containerfile
            == (barebones_tmpcontext / "scratch" / "2.0.0" / "Containerfile.scratch.min").read_text()
        )
        assert (barebones_tmpcontext / "scratch" / "2.0.0" / "Containerfile.scratch.std").is_file()
        assert (
            expected_containerfile
            == (barebones_tmpcontext / "scratch" / "2.0.0" / "Containerfile.scratch.std").read_text()
        )
        assert (barebones_tmpcontext / "scratch" / "2.0.0" / "deps").is_dir()
        assert (barebones_tmpcontext / "scratch" / "2.0.0" / "deps" / "packages.txt").is_file()
        assert (barebones_tmpcontext / "scratch" / "2.0.0" / "test").is_dir()
        assert (barebones_tmpcontext / "scratch" / "2.0.0" / "test" / "goss.yaml").is_file()

    def test_create_version_exists_force(self, barebones_tmpcontext):
        """Test creating an existing version in the BakeryConfig with force works."""
        config = BakeryConfig.from_context(barebones_tmpcontext)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert len(image.versions) == 1

        config.create_version("scratch", "1.0.0", subpath="1", force=True)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert len(image.versions) == 1
        expected_yaml = textwrap.indent(
            textwrap.dedent("""\
              - name: 1.0.0
                subpath: '1'
                latest: true
                os:
                  - name: Scratch
                    primary: true
        """),
            VERSION_INDENT,
        )
        assert expected_yaml in (barebones_tmpcontext / "bakery.yaml").read_text()
        assert (barebones_tmpcontext / "scratch" / "1").is_dir()
        assert (barebones_tmpcontext / "scratch" / "1" / "Containerfile.scratch.min").is_file()
        assert (barebones_tmpcontext / "scratch" / "1" / "Containerfile.scratch.std").is_file()
        assert (
            "COPY scratch/1/deps/packages.txt /tmp/packages.txt"
            in (barebones_tmpcontext / "scratch" / "1" / "Containerfile.scratch.std").read_text()
        )
        assert not (barebones_tmpcontext / "1.0.0").is_dir()

    def test_create_version_not_latest(self, barebones_tmpcontext):
        """Test creating a version and not marking latest does not change latest flag on existing versions."""
        config = BakeryConfig.from_context(barebones_tmpcontext)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert len(image.versions) == 1

        config.create_version("scratch", "2.0.0", latest=False)
        assert len(config.model.images) == 1
        assert len(image.versions) == 2
        expected_yaml = textwrap.indent(
            textwrap.dedent("""
              - name: 2.0.0
                os:
                  - name: Scratch
                    primary: true
        """),
            VERSION_INDENT,
        )
        assert expected_yaml in (barebones_tmpcontext / "bakery.yaml").read_text()
        expected_yaml = textwrap.indent(
            textwrap.dedent("""
              - name: "1.0.0"
                latest: true
                os:
                  - name: "Scratch"
        """),
            VERSION_INDENT,
        )
        assert expected_yaml in (barebones_tmpcontext / "bakery.yaml").read_text()

    def test_create_version_complex(self, basic_tmpcontext):
        """Test creating a new version in the BakeryConfig with more complex files and settings."""
        config = BakeryConfig.from_context(basic_tmpcontext)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert len(image.versions) == 1

        config.create_version("test-image", "2.0.0", subpath="2.0", latest=True)
        assert len(config.model.images) == 1
        assert len(image.versions) == 2
        expected_yaml = textwrap.indent(
            textwrap.dedent("""\
              - name: 2.0.0
                subpath: '2.0'
                latest: true
                os:
                  - name: Ubuntu 22.04
                    primary: true
        """),
            VERSION_INDENT,
        )
        assert expected_yaml in (basic_tmpcontext / "bakery.yaml").read_text()
        assert (basic_tmpcontext / "test-image" / "2.0").is_dir()
        assert (basic_tmpcontext / "test-image" / "2.0" / "Containerfile.ubuntu2204.min").is_file()
        expected_min_containerfile = textwrap.dedent("""\
        FROM docker.io/library/ubuntu:22.04
        LABEL org.opencontainers.image.base.name="docker.io/library/ubuntu:22.04"

        ADD --chmod=750 https://saipittwood.blob.core.windows.net/packages/pti /usr/local/bin/pti

        ### ARG declarations ###
        ARG DEBIAN_FRONTEND=noninteractive
        ARG IMAGE_VERSION="2.0.0"

        ### Install Apt Packages ###
        COPY test-image/2.0/deps/ubuntu2204_packages.txt /tmp/ubuntu2204_packages.txt

        RUN pti container syspkg upgrade --dist \\
            && pti container syspkg install -f /tmp/ubuntu2204_packages.txt \\
            && rm -f /tmp/ubuntu2204_packages.txt \\
            && pti container syspkg clean
        """)
        assert (
            expected_min_containerfile
            == (basic_tmpcontext / "test-image" / "2.0" / "Containerfile.ubuntu2204.min").read_text()
        )
        assert (basic_tmpcontext / "test-image" / "2.0" / "Containerfile.ubuntu2204.std").is_file()
        expected_std_containerfile = textwrap.dedent("""\
        FROM docker.io/library/ubuntu:22.04
        LABEL org.opencontainers.image.base.name="docker.io/library/ubuntu:22.04"

        ADD --chmod=750 https://saipittwood.blob.core.windows.net/packages/pti /usr/local/bin/pti

        ### ARG declarations ###
        ARG DEBIAN_FRONTEND=noninteractive
        ARG IMAGE_VERSION="2.0.0"

        ### Install Apt Packages ###
        COPY test-image/2.0/deps/ubuntu2204_packages.txt /tmp/ubuntu2204_packages.txt
        COPY test-image/2.0/deps/ubuntu2204_optional_packages.txt /tmp/ubuntu2204_optional_packages.txt
        RUN pti container syspkg upgrade --dist \\
            && pti container syspkg install -f /tmp/ubuntu2204_packages.txt \\
            && rm -f /tmp/ubuntu2204_packages.txt \\
            && pti container syspkg install -f /tmp/ubuntu2204_optional_packages.txt \\
            && rm -f /tmp/ubuntu2204_optional_packages.txt \\
            && pti container syspkg clean
        """)
        assert (
            expected_std_containerfile
            == (basic_tmpcontext / "test-image" / "2.0" / "Containerfile.ubuntu2204.std").read_text()
        )
        assert (basic_tmpcontext / "test-image" / "2.0" / "deps").is_dir()
        assert (basic_tmpcontext / "test-image" / "2.0" / "deps" / "ubuntu2204_packages.txt").is_file()
        assert (basic_tmpcontext / "test-image" / "2.0" / "test").is_dir()
        assert (basic_tmpcontext / "test-image" / "2.0" / "test" / "goss.yaml").is_file()

    def test_target_filtering_no_filter(self, testdata_path):
        complex_yaml = testdata_path / "valid" / "complex.yaml"
        config = BakeryConfig(complex_yaml)
        assert len(config.targets) == 10

    def test_target_filtering_filter_image(self, testdata_path):
        complex_yaml = testdata_path / "valid" / "complex.yaml"

        _filter = BakeryConfigFilter(image_name=r"package-manager-init")
        config = BakeryConfig(complex_yaml, _filter=_filter)
        assert len(config.targets) == 2

        _filter = BakeryConfigFilter(image_name=r"^package-manager$")
        config = BakeryConfig(complex_yaml, _filter=_filter)
        assert len(config.targets) == 8

    def test_target_filtering_filter_variant(self, testdata_path):
        complex_yaml = testdata_path / "valid" / "complex.yaml"

        _filter = BakeryConfigFilter(image_variant="std")
        config = BakeryConfig(complex_yaml, _filter=_filter)
        assert len(config.targets) == 6

    def test_target_filtering_filter_version(self, testdata_path):
        complex_yaml = testdata_path / "valid" / "complex.yaml"

        _filter = BakeryConfigFilter(image_version="2025.04.2-8")
        config = BakeryConfig(complex_yaml, _filter=_filter)
        assert len(config.targets) == 6

    def test_target_filtering_filter_os(self, testdata_path):
        complex_yaml = testdata_path / "valid" / "complex.yaml"

        _filter = BakeryConfigFilter(image_os="Ubuntu 24.04")
        config = BakeryConfig(complex_yaml, _filter=_filter)
        assert len(config.targets) == 3

    def test_target_filtering_filter_multi(self, testdata_path):
        complex_yaml = testdata_path / "valid" / "complex.yaml"

        _filter = BakeryConfigFilter(
            image_name=r"^package-manager$", image_version="2025.04.2-8", image_os="Ubuntu 24.04"
        )
        config = BakeryConfig(complex_yaml, _filter=_filter)
        assert len(config.targets) == 2
