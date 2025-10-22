import os
import shutil
import textwrap
from pathlib import Path
from unittest.mock import patch, call

import pytest
from pydantic import ValidationError

import posit_bakery
from posit_bakery.config.config import BakeryConfigDocument, BakeryConfig, BakeryConfigFilter, BakerySettings
from posit_bakery.const import DevVersionInclusionEnum
from test.helpers import (
    yaml_file_testcases,
    FileTestResultEnum,
    IMAGE_INDENT,
    VERSION_INDENT,
    SUCCESS_SUITES,
    TEST_DIRECTORY,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


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

    def test_valid(self, common_image_variants):
        """Test creating a valid BakeryConfigDocument with all fields."""
        base_path = Path(os.getcwd())
        d = BakeryConfigDocument(
            base_path=base_path,
            repository={"url": "https://example.com/repo"},
            registries=[{"host": "registry.example.com", "namespace": "namespace"}],
            images=[{"name": "my-image", "variants": common_image_variants, "versions": [{"name": "1.0.0"}]}],
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

    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    def test_create_image_files_template(self, get_tmpcontext, suite):
        """Test that create_image_files_template creates the correct directory structure."""
        context = get_tmpcontext(suite)
        assert not (context / "new-image").is_dir()
        d = BakeryConfigDocument(base_path=context, repository={"url": "https://example.com/repo"})
        d.create_image_files_template(context / "new-image", "new-image", "ubuntu:22.04")
        assert (context / "new-image").is_dir()
        assert (context / "new-image" / "template" / "Containerfile.jinja2").exists()
        assert (context / "new-image" / "template" / "deps").is_dir()
        assert (context / "new-image" / "template" / "deps" / "packages.txt.jinja2").is_file()
        assert (context / "new-image" / "template" / "test").is_dir()
        assert (context / "new-image" / "template" / "test" / "goss.yaml.jinja2").is_file()

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

    @pytest.mark.parametrize(
        "include_dev_version,clean,expected_versions",
        [
            (DevVersionInclusionEnum.EXCLUDE, True, []),
            (DevVersionInclusionEnum.EXCLUDE, False, []),
            (DevVersionInclusionEnum.INCLUDE, True, ["2024.11.2-9", "2024.11.1-3776"]),
            (DevVersionInclusionEnum.INCLUDE, False, ["2024.11.2-9", "2024.11.1-3776"]),
            (DevVersionInclusionEnum.ONLY, True, ["2024.11.2-9", "2024.11.1-3776"]),
            (DevVersionInclusionEnum.ONLY, False, ["2024.11.2-9", "2024.11.1-3776"]),
        ],
    )
    @patch("atexit.register")
    def test_valid_dev_version_enum(
        self,
        mock_atexit_register,
        include_dev_version,
        clean,
        expected_versions,
        caplog,
        testdata_path,
        patch_requests_get,
    ):
        """Test that the DevVersionInclusionEnum works as expected."""
        yaml_file = testdata_path / "valid" / "complex.yaml"
        with patch.object(posit_bakery.config.image.Image, "create_ephemeral_version_files") as mock_create_files:
            with patch.object(posit_bakery.config.image.Image, "remove_ephemeral_version_files") as mock_remove_files:
                config = BakeryConfig(
                    yaml_file, BakerySettings(dev_versions=include_dev_version, clean_temporary=clean)
                )
                assert config is not None
                assert "WARNING" not in caplog.text
                assert mock_create_files.call_count == len(expected_versions)
                if clean and not include_dev_version == DevVersionInclusionEnum.EXCLUDE:
                    assert mock_atexit_register.call_count == len(expected_versions)
                    expected_calls = [call(mock_remove_files)] * len(expected_versions)
                    mock_atexit_register.assert_has_calls(expected_calls, any_order=True)
                dev_versions = [v for i in config.model.images for v in i.versions if v.isDevelopmentVersion]
                assert len(dev_versions) == len(expected_versions)
                for version in dev_versions:
                    assert version.name in expected_versions
                    assert len(version.os) == 2

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

    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    def test_from_alternate_context(self, suite, project_path, resource_path):
        """Test that a BakeryConfig can be created from a context directory."""
        original_dir = os.getcwd()
        os.chdir(project_path)  # Change to root directory

        context = resource_path / suite
        config = BakeryConfig.from_context(context)
        assert config is not None
        assert config.config_file == context / "bakery.yaml"
        assert config.base_path == context
        assert len(config.model.images) >= 1

        os.chdir(original_dir)  # Change back to original directory

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

    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    def test_create_image_image_exists(self, suite, get_tmpcontext):
        """Test creating a new image in the BakeryConfig."""
        config = BakeryConfig.from_context(get_tmpcontext(suite))
        existing_image_name = config.model.images[0].name
        with pytest.raises(ValueError, match=f"Image '{existing_image_name}' already exists"):
            config.create_image(existing_image_name)

    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    def test_create_image(self, suite, get_tmpcontext):
        """Test creating a new image in the BakeryConfig."""
        context = get_tmpcontext(suite)
        config = BakeryConfig.from_context(context)
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
        assert expected_yaml in (context / "bakery.yaml").read_text()
        assert (context / "new-image").is_dir()
        assert (context / "new-image" / "template").is_dir()
        assert (context / "new-image" / "template" / "Containerfile.jinja2").is_file()

    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    def test_create_image_customized(self, suite, get_tmpcontext):
        """Test creating a new image in the BakeryConfig."""
        context = get_tmpcontext(suite)
        config = BakeryConfig.from_context(context)
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
        assert expected_yaml in (context / "bakery.yaml").read_text()
        assert (context / "image").is_dir()
        assert (context / "image" / "template").is_dir()
        assert (context / "image" / "template" / "Containerfile.jinja2").is_file()
        assert (
            "FROM docker.io/library/ubuntu:24.04"
            in (context / "image" / "template" / "Containerfile.jinja2").read_text()
        )

    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    def test_create_image_nested_subpath(self, suite, get_tmpcontext):
        """Test creating a new image in the BakeryConfig with a nested subpath."""
        context = get_tmpcontext(suite)
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1
        config.create_image(
            "new-image",
            subpath="new/image",
        )
        assert len(config.model.images) == 2
        expected_yaml = textwrap.indent(
            textwrap.dedent("""\
        - name: new-image
          subpath: new/image
        """),
            IMAGE_INDENT,
        )
        assert expected_yaml in (context / "bakery.yaml").read_text()
        assert (context / "new" / "image").is_dir()
        assert (context / "new" / "image" / "template").is_dir()
        assert (context / "new" / "image" / "template" / "Containerfile.jinja2").is_file()

        # Check that the path works correctly in the model.
        image = config.model.get_image("new-image")
        assert image is not None
        assert image.subpath == "new/image"
        assert image.path == (context / "new" / "image")

    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    def test_create_version_exists(self, get_tmpcontext, suite):
        """Test creating an existing version in the BakeryConfig generates an error."""
        context = get_tmpcontext(suite)
        config = BakeryConfig.from_context(context)
        image_name = config.model.images[0].name
        version_name = config.model.images[0].versions[0].name

        with pytest.raises(ValueError, match=f"Version '{version_name}' already exists for image '{image_name}'"):
            config.create_version(image_name, version_name)

    def test_create_version(self, get_tmpcontext):
        """Test creating a new version in the BakeryConfig."""
        context = get_tmpcontext("barebones")
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert len(image.versions) == 1
        version = image.versions[0]
        previous_os = version.os[0]

        new_version = "2.0.0"
        config.create_version(image.name, new_version)
        assert len(config.model.images) == 1
        assert len(image.versions) == 2
        expected_yaml = textwrap.indent(
            textwrap.dedent(f"""\
              - name: 2.0.0
                latest: true
                os:
                  - name: {previous_os.name}
                    primary: true
        """),
            VERSION_INDENT,
        )
        assert expected_yaml in (context / "bakery.yaml").read_text()
        assert (context / image.name / new_version).is_dir()
        assert (context / image.name / new_version / f"Containerfile.{previous_os.extension}").is_file()
        expected_containerfile = textwrap.dedent("""\
        FROM scratch

        COPY scratch/2.0.0/deps/packages.txt /tmp/packages.txt
        """)
        assert expected_containerfile == (context / image.name / new_version / "Containerfile.scratch").read_text()
        assert (context / image.name / new_version / "Containerfile.scratch").is_file()
        assert (context / image.name / new_version / "deps").is_dir()
        assert (context / image.name / new_version / "deps" / "packages.txt").is_file()
        assert (context / image.name / new_version / "test").is_dir()
        assert (context / image.name / new_version / "test" / "goss.yaml").is_file()

    def test_create_version_nested_subpath(self, get_tmpcontext):
        """Test creating a new version in the BakeryConfig with a nested subpath."""
        context = get_tmpcontext("barebones")
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert len(image.versions) == 1

        config.create_version("scratch", "2.0.0", subpath="2/0/0")
        assert len(config.model.images) == 1
        assert len(image.versions) == 2
        expected_yaml = textwrap.indent(
            textwrap.dedent("""\
                - name: 2.0.0
                  subpath: 2/0/0
                  latest: true
                  os:
                    - name: Scratch
                      primary: true
        """),
            VERSION_INDENT,
        )
        assert expected_yaml in (context / "bakery.yaml").read_text()
        assert (context / "scratch" / "2" / "0" / "0").is_dir()
        assert (context / "scratch" / "2" / "0" / "0" / "Containerfile.scratch").is_file()
        expected_containerfile = textwrap.dedent("""\
        FROM scratch

        COPY scratch/2/0/0/deps/packages.txt /tmp/packages.txt
        """)
        assert expected_containerfile == (context / "scratch" / "2" / "0" / "0" / "Containerfile.scratch").read_text()

    def test_create_version_exists_force(self, get_tmpcontext):
        """Test creating an existing version in the BakeryConfig with force works."""
        context = get_tmpcontext("barebones")
        config = BakeryConfig.from_context(context)
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
        assert expected_yaml in (context / "bakery.yaml").read_text()
        assert (context / "scratch" / "1").is_dir()
        assert (context / "scratch" / "1" / "Containerfile.scratch").is_file()
        assert (
            "COPY scratch/1/deps/packages.txt /tmp/packages.txt"
            in (context / "scratch" / "1" / "Containerfile.scratch").read_text()
        )
        assert not (context / "1.0.0").is_dir()

    def test_create_version_not_latest(self, get_tmpcontext):
        """Test creating a version and not marking latest does not change latest flag on existing versions."""
        context = get_tmpcontext("barebones")
        config = BakeryConfig.from_context(context)
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
        assert expected_yaml in (context / "bakery.yaml").read_text()
        expected_yaml = textwrap.indent(
            textwrap.dedent("""
              - name: "1.0.0"
                latest: true
                os:
                  - name: "Scratch"
        """),
            VERSION_INDENT,
        )
        assert expected_yaml in (context / "bakery.yaml").read_text()

    def test_create_version_complex(self, get_tmpcontext):
        """Test creating a new version in the BakeryConfig with more complex files and settings."""
        context = get_tmpcontext("basic")
        config = BakeryConfig.from_context(context)
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
        assert expected_yaml in (context / "bakery.yaml").read_text()
        assert (context / "test-image" / "2.0").is_dir()
        assert (context / "test-image" / "2.0" / "Containerfile.ubuntu2204.min").is_file()
        expected_min_containerfile = textwrap.dedent("""\
        FROM docker.io/library/ubuntu:22.04
        LABEL org.opencontainers.image.base.name="docker.io/library/ubuntu:22.04"

        ### ARG declarations ###
        ARG DEBIAN_FRONTEND=noninteractive
        ARG IMAGE_VERSION="2.0.0"

        ### Install Apt Packages ###
        COPY test-image/2.0/deps/ubuntu2204_packages.txt /tmp/ubuntu2204_packages.txt
        RUN apt-get update -yqq && \\
            apt-get install -yqq --no-install-recommends $(cat /tmp/ubuntu2204_packages.txt) && \\
            rm -f /tmp/ubuntu2204_packages.txt && \\
            apt-get clean -yqq && \\
            rm -rf /var/lib/apt/lists/*

        """)
        assert (
            expected_min_containerfile == (context / "test-image" / "2.0" / "Containerfile.ubuntu2204.min").read_text()
        )
        assert (context / "test-image" / "2.0" / "Containerfile.ubuntu2204.std").is_file()
        expected_std_containerfile = textwrap.dedent("""\
        FROM docker.io/library/ubuntu:22.04
        LABEL org.opencontainers.image.base.name="docker.io/library/ubuntu:22.04"

        ### ARG declarations ###
        ARG DEBIAN_FRONTEND=noninteractive
        ARG IMAGE_VERSION="2.0.0"

        ### Install Apt Packages ###
        COPY test-image/2.0/deps/ubuntu2204_packages.txt /tmp/ubuntu2204_packages.txt
        RUN apt-get update -yqq && \\
            apt-get install -yqq --no-install-recommends $(cat /tmp/ubuntu2204_packages.txt) && \\
            rm -f /tmp/ubuntu2204_packages.txt && \\
            apt-get clean -yqq && \\
            rm -rf /var/lib/apt/lists/*
        COPY test-image/2.0/deps/ubuntu2204_optional_packages.txt /tmp/ubuntu2204_optional_packages.txt
        RUN apt-get update -yqq && \\
            apt-get install -yqq --no-install-recommends $(cat /tmp/ubuntu2204_optional_packages.txt) && \\
            rm -f /tmp/ubuntu2204_optional_packages.txt && \\
            apt-get clean -yqq && \\
            rm -rf /var/lib/apt/lists/*
        """)
        assert (
            expected_std_containerfile == (context / "test-image" / "2.0" / "Containerfile.ubuntu2204.std").read_text()
        )
        assert (context / "test-image" / "2.0" / "deps").is_dir()
        assert (context / "test-image" / "2.0" / "deps" / "ubuntu2204_packages.txt").is_file()
        assert (context / "test-image" / "2.0" / "test").is_dir()
        assert (context / "test-image" / "2.0" / "test" / "goss.yaml").is_file()

    def test_patch_version(self, get_tmpcontext):
        """Test patching an existing version in the BakeryConfig."""
        context = get_tmpcontext("basic")
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert len(image.versions) == 1
        version = image.versions[0]

        config.patch_version(image.name, version.name, "1.0.1")

        # Check for the expected number of model images and versions.
        assert len(config.model.images) == 1
        assert len(image.versions) == 1

        # Check that directory structure has changed as expected.
        assert (context / image.name / "1.0.1").is_dir()
        assert not (context / image.name / "1.0.0").is_dir()
        original_yaml = textwrap.indent(
            textwrap.dedent("""\
              - name: 1.0.0
                latest: true
                os:
                  - name: Ubuntu 22.04
                    primary: true
        """),
            VERSION_INDENT,
        )
        assert original_yaml not in (context / "bakery.yaml").read_text()
        expected_yaml = textwrap.indent(
            textwrap.dedent("""\
              - name: 1.0.1
                latest: true
                os:
                  - name: Ubuntu 22.04
                    primary: true
        """),
            VERSION_INDENT,
        )
        assert expected_yaml in (context / "bakery.yaml").read_text()

        # Check that the files have been rendered correctly.
        assert (context / "test-image" / "1.0.1" / "Containerfile.ubuntu2204.min").is_file()
        expected_min_containerfile = textwrap.dedent("""\
        FROM docker.io/library/ubuntu:22.04
        LABEL org.opencontainers.image.base.name="docker.io/library/ubuntu:22.04"

        ### ARG declarations ###
        ARG DEBIAN_FRONTEND=noninteractive
        ARG IMAGE_VERSION="1.0.1"

        ### Install Apt Packages ###
        COPY test-image/1.0.1/deps/ubuntu2204_packages.txt /tmp/ubuntu2204_packages.txt
        RUN apt-get update -yqq && \\
            apt-get install -yqq --no-install-recommends $(cat /tmp/ubuntu2204_packages.txt) && \\
            rm -f /tmp/ubuntu2204_packages.txt && \\
            apt-get clean -yqq && \\
            rm -rf /var/lib/apt/lists/*

        """)
        assert (
            expected_min_containerfile
            == (context / "test-image" / "1.0.1" / "Containerfile.ubuntu2204.min").read_text()
        )
        assert (context / "test-image" / "1.0.1" / "Containerfile.ubuntu2204.std").is_file()
        expected_std_containerfile = textwrap.dedent("""\
        FROM docker.io/library/ubuntu:22.04
        LABEL org.opencontainers.image.base.name="docker.io/library/ubuntu:22.04"

        ### ARG declarations ###
        ARG DEBIAN_FRONTEND=noninteractive
        ARG IMAGE_VERSION="1.0.1"

        ### Install Apt Packages ###
        COPY test-image/1.0.1/deps/ubuntu2204_packages.txt /tmp/ubuntu2204_packages.txt
        RUN apt-get update -yqq && \\
            apt-get install -yqq --no-install-recommends $(cat /tmp/ubuntu2204_packages.txt) && \\
            rm -f /tmp/ubuntu2204_packages.txt && \\
            apt-get clean -yqq && \\
            rm -rf /var/lib/apt/lists/*
        COPY test-image/1.0.1/deps/ubuntu2204_optional_packages.txt /tmp/ubuntu2204_optional_packages.txt
        RUN apt-get update -yqq && \\
            apt-get install -yqq --no-install-recommends $(cat /tmp/ubuntu2204_optional_packages.txt) && \\
            rm -f /tmp/ubuntu2204_optional_packages.txt && \\
            apt-get clean -yqq && \\
            rm -rf /var/lib/apt/lists/*
        """)
        assert (
            expected_std_containerfile
            == (context / "test-image" / "1.0.1" / "Containerfile.ubuntu2204.std").read_text()
        )
        assert (context / "test-image" / "1.0.1" / "deps").is_dir()
        assert (context / "test-image" / "1.0.1" / "deps" / "ubuntu2204_packages.txt").is_file()
        assert (context / "test-image" / "1.0.1" / "test").is_dir()
        assert (context / "test-image" / "1.0.1" / "test" / "goss.yaml").is_file()

    def test_patch_version_with_dependencies_macros(self, get_tmpcontext):
        """Test patching an existing version in the BakeryConfig when the version has dependencies and macros."""
        context = get_tmpcontext("with-macros")
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert len(image.versions) == 1
        version = image.versions[0]

        config.patch_version(image.name, version.name, "1.0.1")

        # Check for the expected number of model images and versions.
        assert len(config.model.images) == 1
        assert len(image.versions) == 1

        # Check that directory structure has changed as expected.
        assert (context / image.name / "1.0.1").is_dir()
        assert not (context / image.name / "1.0.0").is_dir()
        original_yaml = textwrap.indent(
            textwrap.dedent("""\
              - name: 1.0.0
                latest: true
                os:
                  - name: Ubuntu 22.04
                    primary: true
                dependencies:
                  - dependency: R
                    version: 4.5.1
                  - dependency: python
                    version: 3.13.7
                  - dependency: quarto
                    version: 1.8.24
        """),
            VERSION_INDENT,
        )
        assert original_yaml not in (context / "bakery.yaml").read_text()
        expected_yaml = textwrap.indent(
            textwrap.dedent("""\
              - name: 1.0.1
                latest: true
                os:
                  - name: Ubuntu 22.04
                    primary: true
                dependencies:
                  - dependency: R
                    version: 4.5.1
                  - dependency: python
                    version: 3.13.7
                  - dependency: quarto
                    version: 1.8.24
        """),
            VERSION_INDENT,
        )
        assert expected_yaml in (context / "bakery.yaml").read_text()

        # Check that the files have been rendered correctly.
        assert (context / "test-image" / "1.0.1" / "Containerfile.ubuntu2204.min").is_file()
        expected_min_containerfile = textwrap.dedent("""\
            FROM docker.io/library/ubuntu:22.04
            LABEL org.opencontainers.image.base.name="docker.io/library/ubuntu:22.04"

            ### ARG declarations ###
            ARG DEBIAN_FRONTEND=noninteractive
            ARG IMAGE_VERSION="1.0.1"

            ### Install Apt Packages ###
            RUN apt-get update -yqq --fix-missing && \\
                apt-get upgrade -yqq && \\
                apt-get dist-upgrade -yqq && \\
                apt-get autoremove -yqq --purge && \\
                apt-get install -yqq --no-install-recommends \\
                    curl \\
                    ca-certificates \\
                    gnupg \\
                    tar && \\
                bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.deb.sh')" && \\
                apt-get clean -yqq && \\
                rm -rf /var/lib/apt/lists/*

            COPY test-image/1.0.1/deps/ubuntu2204_packages.txt /tmp/ubuntu2204_packages.txt
            RUN apt-get update -yqq && \\
                xargs -a /tmp/ubuntu2204_packages.txt apt-get install -yqq --no-install-recommends && \\
                apt-get clean -yqq && \\
                rm -rf /var/lib/apt/lists/*
        """)
        assert (
            expected_min_containerfile
            == (context / "test-image" / "1.0.1" / "Containerfile.ubuntu2204.min").read_text()
        )
        assert (context / "test-image" / "1.0.1" / "Containerfile.ubuntu2204.std").is_file()
        expected_std_containerfile = textwrap.dedent("""\
            # Build Python using uv in a separate stage
            FROM ghcr.io/astral-sh/uv:bookworm-slim AS python-builder

            ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
            ENV UV_PYTHON_INSTALL_DIR=/opt/python
            ENV UV_PYTHON_PREFERENCE=only-managed
            RUN uv python install 3.13.7

            FROM docker.io/library/ubuntu:22.04
            LABEL org.opencontainers.image.base.name="docker.io/library/ubuntu:22.04"

            ### ARG declarations ###
            ARG DEBIAN_FRONTEND=noninteractive
            ARG IMAGE_VERSION="1.0.1"

            ### Install Apt Packages ###
            RUN apt-get update -yqq --fix-missing && \\
                apt-get upgrade -yqq && \\
                apt-get dist-upgrade -yqq && \\
                apt-get autoremove -yqq --purge && \\
                apt-get install -yqq --no-install-recommends \\
                    curl \\
                    ca-certificates \\
                    gnupg \\
                    tar && \\
                bash -c "$(curl -1fsSL 'https://dl.posit.co/public/pro/setup.deb.sh')" && \\
                apt-get clean -yqq && \\
                rm -rf /var/lib/apt/lists/*

            COPY test-image/1.0.1/deps/ubuntu2204_packages.txt /tmp/ubuntu2204_packages.txt
            RUN apt-get update -yqq && \\
                xargs -a /tmp/ubuntu2204_packages.txt apt-get install -yqq --no-install-recommends && \\
                apt-get clean -yqq && \\
                rm -rf /var/lib/apt/lists/*

            COPY test-image/1.0.1/deps/ubuntu2204_optional_packages.txt /tmp/ubuntu2204_optional_packages.txt
            RUN apt-get update -yqq && \\
                xargs -a /tmp/ubuntu2204_optional_packages.txt apt-get install -yqq --no-install-recommends && \\
                apt-get clean -yqq && \\
                rm -rf /var/lib/apt/lists/*

            # Install Python from previous stage
            COPY --from=python-builder /opt/python /opt/python

            # Install R
            RUN RUN_UNATTENDED=1 R_VERSION=4.5.1 bash -c "$(curl -fsSL https://rstd.io/r-install)" && \\
                find . -type f -name '[rR]-4.5.1.*\.(deb|rpm)' -delete

            # Install Quarto
            RUN mkdir -p /opt/quarto/1.8.24 && \\
                curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v1.8.24/quarto-1.8.24-linux-amd64.tar.gz" | tar xzf - -C "/opt/quarto/1.8.24" --strip-components=1 && \\
                /opt/quarto/1.8.24/bin/quarto install tinytex --no-prompt --quiet
        """)
        assert (
            expected_std_containerfile
            == (context / "test-image" / "1.0.1" / "Containerfile.ubuntu2204.std").read_text()
        )
        assert (context / "test-image" / "1.0.1" / "deps").is_dir()
        assert (context / "test-image" / "1.0.1" / "deps" / "ubuntu2204_packages.txt").is_file()
        assert (context / "test-image" / "1.0.1" / "test").is_dir()
        assert (context / "test-image" / "1.0.1" / "test" / "goss.yaml").is_file()

    def test_patch_version_subpath(self, get_tmpcontext):
        context = get_tmpcontext("basic")
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert len(image.versions) == 1
        version = image.versions[0]

        old_path = version.path
        config.model.images[0].versions[0].subpath = "1.0"
        shutil.move(old_path, config.model.images[0].versions[0].path)

        config.patch_version(image.name, version.name, "1.0.1")

        # Check for the expected number of model images and versions.
        assert len(config.model.images) == 1
        assert len(image.versions) == 1

        # Check that directory structure has changed as expected.
        assert (context / image.name / "1.0").is_dir()
        original_yaml = textwrap.indent(
            textwrap.dedent("""\
              - name: 1.0.0
                subpath: 1.0
                latest: true
                os:
                  - name: Ubuntu 22.04
                    primary: true
        """),
            VERSION_INDENT,
        )
        assert original_yaml not in (context / "bakery.yaml").read_text()
        expected_yaml = textwrap.indent(
            textwrap.dedent("""\
              - name: 1.0.1
                subpath: '1.0'
                latest: true
                os:
                  - name: Ubuntu 22.04
                    primary: true
        """),
            VERSION_INDENT,
        )
        assert expected_yaml in (context / "bakery.yaml").read_text()

        # Check that the files have been rendered correctly.
        assert (context / "test-image" / "1.0" / "Containerfile.ubuntu2204.min").is_file()
        expected_min_containerfile = textwrap.dedent("""\
        FROM docker.io/library/ubuntu:22.04
        LABEL org.opencontainers.image.base.name="docker.io/library/ubuntu:22.04"

        ### ARG declarations ###
        ARG DEBIAN_FRONTEND=noninteractive
        ARG IMAGE_VERSION="1.0.1"

        ### Install Apt Packages ###
        COPY test-image/1.0/deps/ubuntu2204_packages.txt /tmp/ubuntu2204_packages.txt
        RUN apt-get update -yqq && \\
            apt-get install -yqq --no-install-recommends $(cat /tmp/ubuntu2204_packages.txt) && \\
            rm -f /tmp/ubuntu2204_packages.txt && \\
            apt-get clean -yqq && \\
            rm -rf /var/lib/apt/lists/*

        """)
        assert (
            expected_min_containerfile == (context / "test-image" / "1.0" / "Containerfile.ubuntu2204.min").read_text()
        )
        assert (context / "test-image" / "1.0" / "Containerfile.ubuntu2204.std").is_file()
        expected_std_containerfile = textwrap.dedent("""\
        FROM docker.io/library/ubuntu:22.04
        LABEL org.opencontainers.image.base.name="docker.io/library/ubuntu:22.04"

        ### ARG declarations ###
        ARG DEBIAN_FRONTEND=noninteractive
        ARG IMAGE_VERSION="1.0.1"

        ### Install Apt Packages ###
        COPY test-image/1.0/deps/ubuntu2204_packages.txt /tmp/ubuntu2204_packages.txt
        RUN apt-get update -yqq && \\
            apt-get install -yqq --no-install-recommends $(cat /tmp/ubuntu2204_packages.txt) && \\
            rm -f /tmp/ubuntu2204_packages.txt && \\
            apt-get clean -yqq && \\
            rm -rf /var/lib/apt/lists/*
        COPY test-image/1.0/deps/ubuntu2204_optional_packages.txt /tmp/ubuntu2204_optional_packages.txt
        RUN apt-get update -yqq && \\
            apt-get install -yqq --no-install-recommends $(cat /tmp/ubuntu2204_optional_packages.txt) && \\
            rm -f /tmp/ubuntu2204_optional_packages.txt && \\
            apt-get clean -yqq && \\
            rm -rf /var/lib/apt/lists/*
        """)
        assert (
            expected_std_containerfile == (context / "test-image" / "1.0" / "Containerfile.ubuntu2204.std").read_text()
        )
        assert (context / "test-image" / "1.0" / "deps").is_dir()
        assert (context / "test-image" / "1.0" / "deps" / "ubuntu2204_packages.txt").is_file()
        assert (context / "test-image" / "1.0" / "test").is_dir()
        assert (context / "test-image" / "1.0" / "test" / "goss.yaml").is_file()

    def test_patch_version_clean(self, get_tmpcontext):
        """Test patching an existing version with clean calls shutil.rmtree on the old version path."""
        context = get_tmpcontext("basic")
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert len(image.versions) == 1
        version = image.versions[0]
        original_path = version.path

        with patch("shutil.rmtree") as mock_rmtree:
            config.patch_version(image.name, version.name, "1.0.1", clean=True)
            mock_rmtree.assert_called_once_with(original_path)

    def test_patch_version_clean_subpath(self, get_tmpcontext):
        """Test patching an existing version with clean calls shutil.rmtree on the old version path."""
        context = get_tmpcontext("basic")
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert len(image.versions) == 1
        version = image.versions[0]
        original_path = version.path

        old_path = version.path
        config.model.images[0].versions[0].subpath = "1.0"
        shutil.move(old_path, config.model.images[0].versions[0].path)

        with patch("shutil.rmtree") as mock_rmtree:
            config.patch_version(image.name, version.name, "1.0.1", clean=True)
            mock_rmtree.assert_called_once_with(config.model.images[0].versions[0].path)

    def test_patch_version_no_clean(self, get_tmpcontext):
        """Test patching an existing version without clean calls shutil.move on the old version path."""
        context = get_tmpcontext("basic")
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert len(image.versions) == 1
        version = image.versions[0]
        original_path = version.path

        with patch("shutil.move") as mock_move:
            patched_version = config.patch_version(image.name, version.name, "1.0.1", clean=False)
            mock_move.assert_called_once_with(original_path, patched_version.path)

    def test_patch_version_image_does_not_exist(self, get_tmpcontext):
        """Test patching a version for a non-existent image in the BakeryConfig generates an error."""
        context = get_tmpcontext("basic")
        config = BakeryConfig.from_context(context)

        with pytest.raises(ValueError, match="Image 'non-existent-image' does not exist in the config"):
            config.patch_version("non-existent-image", "1.0.0", "1.0.1")

    def test_patch_version_does_not_exist(self, get_tmpcontext):
        """Test patching a non-existent version in the BakeryConfig generates an error."""
        context = get_tmpcontext("basic")
        config = BakeryConfig.from_context(context)

        with pytest.raises(
            ValueError, match=f"Version '9.9.9' does not exist for image '{config.model.images[0].name}'"
        ):
            config.patch_version(config.model.images[0].name, "9.9.9", "10.0.0")

    def test_patch_version_new_version_already_exists(self, get_tmpcontext):
        """Test patching a version to a new version that already exists in the BakeryConfig generates an error."""
        context = get_tmpcontext("basic")
        config = BakeryConfig.from_context(context)
        image = config.model.images[0]
        version = image.versions[0]

        config.create_version(image.name, "2.0.0")

        with pytest.raises(ValueError, match=f"Version '2.0.0' already exists in image '{image.name}'"):
            config.patch_version(image.name, version.name, "2.0.0")

    def test_target_filtering_no_filter(self, testdata_path):
        complex_yaml = testdata_path / "valid" / "complex.yaml"
        config = BakeryConfig(complex_yaml)
        assert len(config.targets) == 10

    def test_target_filtering_filter_image(self, testdata_path):
        complex_yaml = testdata_path / "valid" / "complex.yaml"

        settings = BakerySettings(filter=BakeryConfigFilter(image_name=r"package-manager-init"))
        config = BakeryConfig(complex_yaml, settings)
        assert len(config.targets) == 2

        settings = BakerySettings(filter=BakeryConfigFilter(image_name=r"^package-manager$"))
        config = BakeryConfig(complex_yaml, settings)
        assert len(config.targets) == 8

    def test_target_filtering_filter_variant(self, testdata_path):
        complex_yaml = testdata_path / "valid" / "complex.yaml"

        settings = BakerySettings(filter=BakeryConfigFilter(image_variant="std"))
        config = BakeryConfig(complex_yaml, settings)
        assert len(config.targets) == 6

    def test_target_filtering_filter_version(self, testdata_path):
        complex_yaml = testdata_path / "valid" / "complex.yaml"

        settings = BakerySettings(filter=BakeryConfigFilter(image_version="2025.04.2-8"))
        config = BakeryConfig(complex_yaml, settings)
        assert len(config.targets) == 6

    def test_target_filtering_filter_os(self, testdata_path):
        complex_yaml = testdata_path / "valid" / "complex.yaml"

        settings = BakerySettings(filter=BakeryConfigFilter(image_os="Ubuntu 24.04"))
        config = BakeryConfig(complex_yaml, settings)
        assert len(config.targets) == 3

    def test_target_filtering_filter_multi(self, testdata_path):
        complex_yaml = testdata_path / "valid" / "complex.yaml"

        settings = BakerySettings(
            filter=BakeryConfigFilter(
                image_name=r"^package-manager$", image_version="2025.04.2-8", image_os="Ubuntu 24.04"
            )
        )
        config = BakeryConfig(complex_yaml, settings)
        assert len(config.targets) == 2

    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    def test_remove_image(self, suite, get_tmpcontext):
        """Test removing an image from the BakeryConfig."""
        context = get_tmpcontext(suite)
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1
        image_name = config.model.images[0].name
        image_path = context / image_name

        # Verify the image exists
        assert image_path.is_dir()
        assert config.model.get_image(image_name) is not None

        # Remove the image
        config.remove_image(image_name)

        # Verify the image has been removed
        assert len(config.model.images) == 0
        assert not image_path.is_dir()
        assert config.model.get_image(image_name) is None

        # Verify the config file has been updated
        yaml_content = (context / "bakery.yaml").read_text()
        assert f"- name: {image_name}" not in yaml_content

    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    def test_remove_image_with_subpath(self, suite, get_tmpcontext):
        """Test removing an image with a custom subpath from the BakeryConfig."""
        context = get_tmpcontext(suite)
        config = BakeryConfig.from_context(context)

        # Create a new image with a subpath
        config.create_image("new-image", subpath="custom/path")
        assert len(config.model.images) == 2
        image_path = context / "custom" / "path"
        assert image_path.is_dir()

        # Remove the image
        config.remove_image("new-image")

        # Verify the image has been removed
        assert len(config.model.images) == 1
        assert not image_path.is_dir()
        assert config.model.get_image("new-image") is None

        # Verify the config file has been updated
        yaml_content = (context / "bakery.yaml").read_text()
        assert "- name: new-image" not in yaml_content

    def test_remove_image_does_not_exist(self, get_tmpcontext):
        """Test removing a non-existent image raises an error."""
        context = get_tmpcontext("basic")
        config = BakeryConfig.from_context(context)

        with pytest.raises(ValueError, match="Image 'non-existent' does not exist in the config"):
            config.remove_image("non-existent")

    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    def test_remove_version(self, suite, get_tmpcontext):
        """Test removing a version from an image in the BakeryConfig."""
        context = get_tmpcontext(suite)
        config = BakeryConfig.from_context(context)
        image = config.model.images[0]
        version = image.versions[0]

        # Create a second version so the image isn't left without versions
        config.create_version(image.name, "2.0.0")
        assert len(image.versions) == 2

        # Remove the first version
        config.remove_version(image.name, version.name)

        # Verify the version has been removed
        assert len(image.versions) == 1
        assert image.get_version(version.name) is None
        version_path = context / image.name / version.name
        assert not version_path.is_dir()

        # Verify the config file has been updated
        yaml_content = (context / "bakery.yaml").read_text()
        # The version name might still appear in the remaining version, so we check more specifically
        config_reloaded = BakeryConfig.from_context(context)
        reloaded_image = config_reloaded.model.get_image(image.name)
        assert reloaded_image.get_version(version.name) is None
        assert reloaded_image.get_version("2.0.0") is not None

    def test_remove_version_with_subpath(self, get_tmpcontext):
        """Test removing a version with a custom subpath from an image in the BakeryConfig."""
        context = get_tmpcontext("basic")
        config = BakeryConfig.from_context(context)
        image = config.model.images[0]

        # Create a version with a subpath
        config.create_version(image.name, "2.0.0", subpath="2/0/0")
        assert len(image.versions) == 2
        version_path = context / image.name / "2" / "0" / "0"
        assert version_path.is_dir()

        # Remove the version
        config.remove_version(image.name, "2.0.0")

        # Verify the version has been removed
        assert len(image.versions) == 1
        assert image.get_version("2.0.0") is None
        assert not version_path.is_dir()

        # Verify the config file has been updated
        config_reloaded = BakeryConfig.from_context(context)
        reloaded_image = config_reloaded.model.get_image(image.name)
        assert reloaded_image.get_version("2.0.0") is None

    def test_remove_version_image_does_not_exist(self, get_tmpcontext):
        """Test removing a version from a non-existent image raises an error."""
        context = get_tmpcontext("basic")
        config = BakeryConfig.from_context(context)

        with pytest.raises(ValueError, match="Image 'non-existent' does not exist in the config"):
            config.remove_version("non-existent", "1.0.0")

    def test_remove_version_does_not_exist(self, get_tmpcontext):
        """Test removing a non-existent version raises an error."""
        context = get_tmpcontext("basic")
        config = BakeryConfig.from_context(context)
        image_name = config.model.images[0].name

        with pytest.raises(ValueError, match=f"Version 'non-existent' does not exist for image '{image_name}'"):
            config.remove_version(image_name, "non-existent")
