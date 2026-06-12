import json
import os
import shutil
import textwrap
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch, call

import pytest
from pydantic import ValidationError

import posit_bakery
from posit_bakery.config.config import (
    BakeryConfigDocument,
    BakeryConfig,
    BakeryConfigFilter,
    BakerySettings,
    _apply_dev_spec,
    _extract_calver_minor,
)
from posit_bakery.config.image.dev_version.spec import DevBuildSpec
from posit_bakery.config.dependencies import PythonDependencyConstraint, RDependencyVersions
from posit_bakery.config.image.posit_product.const import ReleaseChannelEnum
from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
from posit_bakery.error import BakeryError
from posit_bakery.image.image_metadata import BuildMetadata
from test.config.conftest import CONFIG_TESTDATA_DIR
from test.helpers import (
    yaml_file_testcases,
    FileTestResultEnum,
    IMAGE_INDENT,
    VERSION_INDENT,
    SUCCESS_SUITES,
    assert_directories_match,
    MATRIX_INDENT,
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

    def test_registry_with_repository_field_invalid(self):
        """Test that specifying a registry with a repository field fails validation."""
        base_path = Path(os.getcwd())
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            BakeryConfigDocument(
                base_path=base_path,
                repository={"url": "https://example.com/repo"},
                registries=[{"host": "registry.example.com", "namespace": "namespace", "repository": "my-repo"}],
            )


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
            (DevVersionInclusionEnum.INCLUDE, True, ["2026.02.0-dev+89-ga1b2c3d4e5", "2026.01.0-dev+167-gd27bbec1d7"]),
            (DevVersionInclusionEnum.INCLUDE, False, ["2026.02.0-dev+89-ga1b2c3d4e5", "2026.01.0-dev+167-gd27bbec1d7"]),
            (DevVersionInclusionEnum.ONLY, True, ["2026.02.0-dev+89-ga1b2c3d4e5", "2026.01.0-dev+167-gd27bbec1d7"]),
            (DevVersionInclusionEnum.ONLY, False, ["2026.02.0-dev+89-ga1b2c3d4e5", "2026.01.0-dev+167-gd27bbec1d7"]),
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
        with patch.object(posit_bakery.config.image.Image, "render_ephemeral_version_files") as mock_create_files:
            with patch.object(posit_bakery.config.image.Image, "remove_ephemeral_version_files") as mock_remove_files:
                config = BakeryConfig(
                    yaml_file, BakerySettings(dev_versions=include_dev_version, clean_temporary=clean)
                )
                assert config is not None
                assert "WARNING" not in caplog.text
                if include_dev_version != DevVersionInclusionEnum.EXCLUDE:
                    assert mock_create_files.call_count == len(config.model.images)
                if clean and not include_dev_version == DevVersionInclusionEnum.EXCLUDE:
                    assert mock_atexit_register.call_count == len(config.model.images)
                    expected_calls = [call(mock_remove_files)] * len(config.model.images)
                    mock_atexit_register.assert_has_calls(expected_calls, any_order=True)
                dev_versions = [v for i in config.model.images for v in i.versions if v.isDevelopmentVersion]
                assert len(dev_versions) == len(expected_versions)
                for version in dev_versions:
                    assert version.name in expected_versions
                    assert len(version.os) == 2

    @pytest.mark.parametrize(
        "dev_channel,expected_dev_version_count",
        [
            pytest.param(None, 2, id="no-filter-includes-all-dev-versions"),
            pytest.param(ReleaseChannelEnum.PREVIEW, 1, id="preview-filter"),
            pytest.param(ReleaseChannelEnum.DAILY, 1, id="daily-filter"),
            pytest.param(ReleaseChannelEnum.RELEASE, 0, id="release-filter-no-match"),
        ],
    )
    @patch("atexit.register")
    def test_dev_channel_filter(
        self,
        mock_atexit_register,
        dev_channel,
        expected_dev_version_count,
        testdata_path,
        patch_requests_get,
    ):
        """Test that dev_channel filters development versions by release channel."""
        yaml_file = testdata_path / "valid" / "complex.yaml"
        with patch.object(posit_bakery.config.image.Image, "render_ephemeral_version_files"):
            with patch.object(posit_bakery.config.image.Image, "remove_ephemeral_version_files"):
                config = BakeryConfig(
                    yaml_file,
                    BakerySettings(
                        dev_versions=DevVersionInclusionEnum.ONLY,
                        dev_channel=dev_channel,
                        clean_temporary=False,
                    ),
                )
                dev_targets = [t for t in config.targets if t.image_version.isDevelopmentVersion]
                # package-manager has 2 variants and each dev version has 2 OSes = 4 targets per dev version
                assert len(dev_targets) == expected_dev_version_count * 4

    @patch("atexit.register")
    def test_dev_channel_filter_with_include(
        self,
        mock_atexit_register,
        testdata_path,
        patch_requests_get,
    ):
        """Test that dev_channel filters work with dev_versions=INCLUDE (mixed dev + release)."""
        yaml_file = testdata_path / "valid" / "complex.yaml"
        with patch.object(posit_bakery.config.image.Image, "render_ephemeral_version_files"):
            with patch.object(posit_bakery.config.image.Image, "remove_ephemeral_version_files"):
                config = BakeryConfig(
                    yaml_file,
                    BakerySettings(
                        dev_versions=DevVersionInclusionEnum.INCLUDE,
                        dev_channel=ReleaseChannelEnum.DAILY,
                        clean_temporary=False,
                    ),
                )
                dev_targets = [t for t in config.targets if t.image_version.isDevelopmentVersion]
                release_targets = [t for t in config.targets if not t.image_version.isDevelopmentVersion]
                # Only daily dev versions included (1 dev version × 2 variants × 2 OSes = 4)
                assert len(dev_targets) == 4
                # Release versions still present
                assert len(release_targets) > 0

    @patch("atexit.register")
    def test_latest_excludes_development_versions(
        self,
        mock_atexit_register,
        testdata_path,
        patch_requests_get,
    ):
        """Test that --latest with --dev-versions include excludes development versions."""
        yaml_file = testdata_path / "valid" / "complex.yaml"
        with patch.object(posit_bakery.config.image.Image, "render_ephemeral_version_files"):
            with patch.object(posit_bakery.config.image.Image, "remove_ephemeral_version_files"):
                config = BakeryConfig(
                    yaml_file,
                    BakerySettings(
                        dev_versions=DevVersionInclusionEnum.INCLUDE,
                        latest=True,
                        clean_temporary=False,
                        filter=BakeryConfigFilter(image_name="^package-manager$"),
                    ),
                )
                # Targets are produced.
                assert len(config.targets) > 0
                # No target is a development version (the dev versions loaded by
                # --dev-versions include are excluded by --latest).
                assert all(not t.image_version.isDevelopmentVersion for t in config.targets)
                # Every target is the latest release version.
                assert all(t.image_version.name == "2025.04.2-8" for t in config.targets)

    @pytest.mark.parametrize(
        "dev_versions",
        [DevVersionInclusionEnum.INCLUDE, DevVersionInclusionEnum.ONLY],
    )
    @patch("atexit.register")
    def test_latest_warns_when_combined_with_dev_inclusion(
        self,
        mock_atexit_register,
        caplog,
        testdata_path,
        patch_requests_get,
        dev_versions,
    ):
        """Test that --latest with --dev-versions include/only warns that dev versions are ignored."""
        yaml_file = testdata_path / "valid" / "complex.yaml"
        with patch.object(posit_bakery.config.image.Image, "render_ephemeral_version_files"):
            with patch.object(posit_bakery.config.image.Image, "remove_ephemeral_version_files"):
                BakeryConfig(
                    yaml_file,
                    BakerySettings(
                        dev_versions=dev_versions,
                        latest=True,
                        clean_temporary=False,
                    ),
                )
        assert "WARNING" in caplog.text
        assert "--latest ignores development versions" in caplog.text
        assert dev_versions.value in caplog.text

    @pytest.mark.usefixtures("patch_requests_get")
    def test_latest_no_warning_when_dev_versions_excluded(self, caplog, testdata_path):
        """Test that --latest with the default --dev-versions exclude emits no dev-version warning."""
        yaml_file = testdata_path / "valid" / "complex.yaml"
        BakeryConfig(yaml_file, BakerySettings(latest=True))
        assert "--latest ignores development versions" not in caplog.text

    def test_dev_channel_warning_when_dev_versions_excluded(
        self,
        caplog,
        testdata_path,
        patch_requests_get,
    ):
        """Test that a warning is emitted when --dev-channel is set but dev versions are excluded."""
        yaml_file = testdata_path / "valid" / "complex.yaml"
        BakeryConfig(
            yaml_file,
            BakerySettings(
                dev_versions=DevVersionInclusionEnum.EXCLUDE,
                dev_channel=ReleaseChannelEnum.DAILY,
            ),
        )
        assert "WARNING" in caplog.text
        assert "--dev-channel" in caplog.text

    def test_dev_stream_constructor_arg_migrates_to_dev_channel(self):
        """BakerySettings(dev_stream=...) must migrate the value to dev_channel with a warning."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            settings = BakerySettings(dev_stream=ReleaseChannelEnum.DAILY)
        assert settings.dev_channel == ReleaseChannelEnum.DAILY
        assert any("dev_stream" in str(warning.message).lower() for warning in w)
        assert any(issubclass(warning.category, DeprecationWarning) for warning in w)

    def test_dev_channel_wins_when_both_provided(self):
        """When both dev_stream and dev_channel are provided, dev_channel wins."""
        settings = BakerySettings(
            dev_channel=ReleaseChannelEnum.PREVIEW,
            dev_stream=ReleaseChannelEnum.DAILY,
        )
        assert settings.dev_channel == ReleaseChannelEnum.PREVIEW

    def test_dev_stream_migrates_when_dev_channel_is_explicit_none(self):
        """dev_stream must migrate even when dev_channel=None is passed explicitly."""
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            settings = BakerySettings(dev_stream=ReleaseChannelEnum.DAILY, dev_channel=None)
        assert settings.dev_channel == ReleaseChannelEnum.DAILY
        assert any(issubclass(warning.category, DeprecationWarning) for warning in w)

    class TestDevBuildSpecApplication:
        def test_inert_when_no_spec(self, testdata_path, patch_requests_get):
            """No dev_spec: config loads normally, no version_override set on channel devVersions."""
            from posit_bakery.config.image.dev_version import ImageDevelopmentVersionFromProductChannel

            yaml_file = testdata_path / "valid" / "complex.yaml"
            with patch.object(posit_bakery.config.image.Image, "render_ephemeral_version_files"):
                with patch.object(posit_bakery.config.image.Image, "remove_ephemeral_version_files"):
                    config = BakeryConfig(
                        yaml_file,
                        settings=BakerySettings(dev_versions=DevVersionInclusionEnum.ONLY),
                    )
            for image in config.model.images:
                for dv in image.devVersions:
                    if isinstance(dv, ImageDevelopmentVersionFromProductChannel):
                        assert dv.version_override is None

        def test_pins_version_on_matching_channel(self, testdata_path, patch_requests_get):
            """dev_spec pins the matching stream dev version before resolution."""
            from posit_bakery.config.image.dev_version.spec import DevBuildSpec

            yaml_file = testdata_path / "valid" / "complex.yaml"
            spec = DevBuildSpec(version="2026.05.0-dev+999-gSHA", channel=ReleaseChannelEnum.DAILY)
            settings = BakerySettings(
                dev_versions=DevVersionInclusionEnum.ONLY,
                dev_spec=spec,
            )
            with patch.object(posit_bakery.config.image.Image, "render_ephemeral_version_files"):
                with patch.object(posit_bakery.config.image.Image, "remove_ephemeral_version_files"):
                    config = BakeryConfig(yaml_file, settings=settings)
            pinned = [
                dv for image in config.model.images for dv in image.devVersions if dv.version_override is not None
            ]
            assert len(pinned) == 1
            assert pinned[0].version_override == "2026.05.0-dev+999-gSHA"

        def test_ambiguity_raises_when_no_channel(self, tmp_path, patch_requests_get):
            """dev_spec without channel raises when image has two stream dev versions."""
            from posit_bakery.config.image.dev_version.spec import DevBuildSpec

            bakery_yaml = tmp_path / "bakery.yaml"
            bakery_yaml.write_text(
                "repository:\n"
                "  url: https://github.com/posit-dev/test\n"
                "images:\n"
                "  - name: test-image\n"
                "    devVersions:\n"
                "      - sourceType: stream\n"
                "        product: package-manager\n"
                "        channel: daily\n"
                "        os:\n"
                "          - name: Ubuntu 24.04\n"
                "            primary: true\n"
                "      - sourceType: stream\n"
                "        product: package-manager\n"
                "        channel: preview\n"
                "        os:\n"
                "          - name: Ubuntu 24.04\n"
                "            primary: true\n"
            )
            spec = DevBuildSpec(version="2026.05.0-dev+999-gSHA")
            settings = BakerySettings(dev_versions=DevVersionInclusionEnum.ONLY, dev_spec=spec)
            with pytest.raises(ValueError, match="[Aa]mbig"):
                BakeryConfig(bakery_yaml, settings=settings)

        def test_conflicting_channels_raise(self, tmp_path, patch_requests_get):
            """dev_spec.channel and --dev-channel must not conflict."""
            from posit_bakery.config.image.dev_version.spec import DevBuildSpec

            bakery_yaml = tmp_path / "bakery.yaml"
            bakery_yaml.write_text(
                "repository:\n"
                "  url: https://github.com/posit-dev/test\n"
                "images:\n"
                "  - name: test-image\n"
                "    devVersions:\n"
                "      - sourceType: stream\n"
                "        product: package-manager\n"
                "        channel: daily\n"
                "        os:\n"
                "          - name: Ubuntu 24.04\n"
                "            primary: true\n"
            )
            spec = DevBuildSpec(version="2026.05.0-dev+999-gSHA", channel=ReleaseChannelEnum.DAILY)
            settings = BakerySettings(
                dev_versions=DevVersionInclusionEnum.ONLY,
                dev_spec=spec,
                dev_channel=ReleaseChannelEnum.PREVIEW,  # conflicts with spec.channel
            )
            with pytest.raises(ValueError, match="[Cc]onfli"):
                BakeryConfig(bakery_yaml, settings=settings)

        def test_no_channel_spec_pins_sole_stream_devversion(self, tmp_path, patch_requests_get):
            """dev_spec without channel pins the one stream devVersion when unambiguous."""
            from posit_bakery.config.image.dev_version import ImageDevelopmentVersionFromProductChannel
            from posit_bakery.config.image.dev_version.spec import DevBuildSpec

            bakery_yaml = tmp_path / "bakery.yaml"
            bakery_yaml.write_text(
                "repository:\n"
                "  url: https://github.com/posit-dev/test\n"
                "images:\n"
                "  - name: test-image\n"
                "    devVersions:\n"
                "      - sourceType: stream\n"
                "        product: package-manager\n"
                "        channel: daily\n"
                "        os:\n"
                "          - name: Ubuntu 24.04\n"
                "            primary: true\n"
            )
            spec = DevBuildSpec(version="2026.05.0-dev+999-gSHA")
            settings = BakerySettings(dev_versions=DevVersionInclusionEnum.ONLY, dev_spec=spec)
            with patch.object(posit_bakery.config.image.Image, "render_ephemeral_version_files"):
                with patch.object(posit_bakery.config.image.Image, "remove_ephemeral_version_files"):
                    config = BakeryConfig(bakery_yaml, settings=settings)
            pinned = [
                dv
                for image in config.model.images
                for dv in image.devVersions
                if isinstance(dv, ImageDevelopmentVersionFromProductChannel) and dv.version_override is not None
            ]
            assert len(pinned) == 1
            assert pinned[0].version_override == "2026.05.0-dev+999-gSHA"

    @pytest.mark.parametrize(
        "include_matrix_versions,expected_uids",
        [
            pytest.param(
                MatrixVersionInclusionEnum.EXCLUDE,
                [],
                id="exclude-matrix-versions",
            ),
            pytest.param(
                MatrixVersionInclusionEnum.INCLUDE,
                [
                    "session-r4-5-1-python3-13-7-quarto1-7-34-ubuntu-24-04",
                    "session-r4-5-1-python3-12-11-quarto1-7-34-ubuntu-24-04",
                    "session-r4-4-3-python3-13-7-quarto1-7-34-ubuntu-24-04",
                    "session-r4-4-3-python3-12-11-quarto1-7-34-ubuntu-24-04",
                ],
                id="include-matrix-versions",
            ),
            pytest.param(
                MatrixVersionInclusionEnum.ONLY,
                [
                    "session-r4-5-1-python3-13-7-quarto1-7-34-ubuntu-24-04",
                    "session-r4-5-1-python3-12-11-quarto1-7-34-ubuntu-24-04",
                    "session-r4-4-3-python3-13-7-quarto1-7-34-ubuntu-24-04",
                    "session-r4-4-3-python3-12-11-quarto1-7-34-ubuntu-24-04",
                ],
                id="only-matrix-versions",
            ),
        ],
    )
    @pytest.mark.usefixtures("patch_requests_get")
    def test_valid_matrix_version_enum(
        self,
        include_matrix_versions,
        expected_uids,
        caplog,
        testdata_path,
    ):
        """Test that the DevVersionInclusionEnum works as expected."""
        yaml_file = testdata_path / "valid" / "complex.yaml"
        config = BakeryConfig(yaml_file, BakerySettings(matrix_versions=include_matrix_versions))
        assert config is not None
        assert "WARNING" not in caplog.text
        matrix_versions = [t for t in config.targets if t.image_version.isMatrixVersion]
        assert len(matrix_versions) == len(expected_uids)
        if include_matrix_versions == MatrixVersionInclusionEnum.INCLUDE:
            assert len(config.targets) > len(matrix_versions)
        elif include_matrix_versions == MatrixVersionInclusionEnum.ONLY:
            assert len(config.targets) == len(matrix_versions)
        for target in matrix_versions:
            assert target.uid in expected_uids

    @pytest.mark.usefixtures("patch_requests_get")
    def test_latest_filters_standard_versions(self, testdata_path):
        """--latest keeps only the standard version marked latest: true."""
        yaml_file = testdata_path / "valid" / "complex.yaml"
        config = BakeryConfig(
            yaml_file,
            BakerySettings(
                filter=BakeryConfigFilter(image_name="^package-manager$"),
                latest=True,
            ),
        )
        assert len(config.targets) > 0
        assert all(t.image_version.name == "2025.04.2-8" for t in config.targets)
        assert all(t.image_version.latest for t in config.targets)

    @pytest.mark.usefixtures("patch_requests_get")
    def test_latest_filters_matrix_versions(self, testdata_path):
        """--latest with matrix included keeps only the latest matrix combination."""
        yaml_file = testdata_path / "valid" / "complex.yaml"
        config = BakeryConfig(
            yaml_file,
            BakerySettings(
                filter=BakeryConfigFilter(image_name="^session$"),
                matrix_versions=MatrixVersionInclusionEnum.ONLY,
                latest=True,
            ),
        )
        assert len(config.targets) == 1
        target = config.targets[0]
        assert target.image_version.latest
        assert target.uid == "session-r4-5-1-python3-13-7-quarto1-7-34-ubuntu-24-04"

    @pytest.mark.usefixtures("patch_requests_get")
    def test_latest_warns_when_image_version_filter_matches_excluded(self, caplog, testdata_path):
        """A warning is logged when --image-version matches a version excluded by --latest."""
        yaml_file = testdata_path / "valid" / "complex.yaml"
        config = BakeryConfig(
            yaml_file,
            BakerySettings(
                filter=BakeryConfigFilter(image_name="^package-manager$", image_version="2024.11.0-7"),
                latest=True,
            ),
        )
        assert len(config.targets) == 0
        assert "WARNING" in caplog.text
        assert "Version '2024.11.0-7' in image 'package-manager' matches --image-version filter" in caplog.text
        assert "not the latest version (excluded by --latest)" in caplog.text

    @pytest.mark.usefixtures("patch_requests_get")
    def test_filter_warning_matrix_image_excluded_by_default(self, caplog, testdata_path):
        """Test that a warning is logged when --image-name matches a matrix image but it's excluded by default."""
        yaml_file = testdata_path / "valid" / "complex.yaml"
        config = BakeryConfig(
            yaml_file,
            BakerySettings(
                filter=BakeryConfigFilter(image_name="^session$"),
                matrix_versions=MatrixVersionInclusionEnum.EXCLUDE,
            ),
        )
        assert config is not None
        assert len(config.targets) == 0
        assert "WARNING" in caplog.text
        assert "Image 'session' matches --image-name filter but is being skipped" in caplog.text
        assert "matrix image excluded by default" in caplog.text

    @pytest.mark.usefixtures("patch_requests_get")
    def test_settings_latest_defaults_false(self):
        """The latest setting defaults to False and accepts True."""
        assert BakerySettings().latest is False
        assert BakerySettings(latest=True).latest is True

    @pytest.mark.usefixtures("patch_requests_get")
    def test_filter_warning_non_matrix_image_excluded_by_matrix_only(self, caplog, testdata_path):
        """Test that a warning is logged when --image-name matches a non-matrix image but --matrix-versions only is set."""
        yaml_file = testdata_path / "valid" / "complex.yaml"
        config = BakeryConfig(
            yaml_file,
            BakerySettings(
                filter=BakeryConfigFilter(image_name="^package-manager$"),
                matrix_versions=MatrixVersionInclusionEnum.ONLY,
            ),
        )
        assert config is not None
        assert len(config.targets) == 0
        assert "WARNING" in caplog.text
        assert "Image 'package-manager' matches --image-name filter but is being skipped" in caplog.text
        assert "non-matrix image excluded by --matrix-versions only" in caplog.text

    @pytest.mark.usefixtures("patch_requests_get")
    def test_filter_warning_version_excluded_by_dev_versions_only(self, caplog, testdata_path):
        """Test that a warning is logged when --image-version matches but --dev-versions only excludes it."""
        yaml_file = testdata_path / "valid" / "complex.yaml"
        with patch.object(posit_bakery.config.image.Image, "render_ephemeral_version_files"):
            config = BakeryConfig(
                yaml_file,
                BakerySettings(
                    filter=BakeryConfigFilter(image_name="^package-manager$", image_version="2025.04.2-8"),
                    dev_versions=DevVersionInclusionEnum.ONLY,
                ),
            )
        assert config is not None
        assert len(config.targets) == 0
        assert "WARNING" in caplog.text
        assert "Version '2025.04.2-8' in image 'package-manager' matches --image-version filter" in caplog.text
        assert "not a development version" in caplog.text

    @pytest.mark.usefixtures("patch_requests_get")
    def test_filter_warning_image_matches_but_no_targets(self, caplog, testdata_path):
        """Test that a warning is logged when --image-name matches but all versions are filtered out."""
        yaml_file = testdata_path / "valid" / "complex.yaml"
        config = BakeryConfig(
            yaml_file,
            BakerySettings(
                filter=BakeryConfigFilter(image_name="^package-manager$", image_version="nonexistent"),
            ),
        )
        assert config is not None
        assert len(config.targets) == 0
        assert "WARNING" in caplog.text
        assert "Image 'package-manager' matches --image-name filter but yielded no targets" in caplog.text

    @pytest.mark.usefixtures("patch_requests_get")
    def test_filter_no_warning_when_targets_generated(self, caplog, testdata_path):
        """Test that no warning is logged when filters match and targets are generated."""
        yaml_file = testdata_path / "valid" / "complex.yaml"
        config = BakeryConfig(
            yaml_file,
            BakerySettings(
                filter=BakeryConfigFilter(image_name="^package-manager$", image_version="2025.04.2-8"),
            ),
        )
        assert config is not None
        assert len(config.targets) > 0
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

    def test_create_version_no_mark_latest(self, get_tmpcontext):
        """Test that --no-mark-latest preserves the existing latest flag."""
        context = get_tmpcontext("basic")
        config = BakeryConfig.from_context(context)
        image = config.model.images[0]
        assert image.versions[0].latest is True

        config.create_version("test-image", "2.0.0", subpath="2.0", latest=False)

        # The old version should still be latest in both the model and YAML.
        assert image.get_version("1.0.0").latest is True
        assert image.get_version("2.0.0").latest is False

        yaml_text = (context / "bakery.yaml").read_text()
        expected_old = textwrap.indent(
            textwrap.dedent("""\
              - name: 1.0.0
                latest: true
                os:
                  - name: Ubuntu 22.04
                    primary: true
        """),
            VERSION_INDENT,
        )
        assert expected_old in yaml_text

        # The new version should NOT have latest in the YAML.
        expected_new = textwrap.indent(
            textwrap.dedent("""\
              - name: 2.0.0
                subpath: '2.0'
                os:
                  - name: Ubuntu 22.04
                    primary: true
        """),
            VERSION_INDENT,
        )
        assert expected_new in yaml_text

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
                    version: 1.8.27
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
                    version: 1.8.27
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
            ARG BUILDARCH
            ARG TARGETARCH=${BUILDARCH}

            ### Install Apt Packages ###
            RUN echo 'Acquire::Retries "3"; Acquire::http::Timeout "30"; Acquire::https::Timeout "30";' > /etc/apt/apt.conf.d/99-retries && \\
                apt-get update -yqq --fix-missing && \\
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
            FROM ghcr.io/astral-sh/uv:debian-slim AS python-builder

            ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
            ENV UV_PYTHON_INSTALL_DIR=/opt/python
            ENV UV_PYTHON_PREFERENCE=only-managed
            RUN uv python install 3.13.7
            RUN mv /opt/python/cpython-3.13.7-linux-*/ /opt/python/3.13.7


            FROM docker.io/library/ubuntu:22.04
            LABEL org.opencontainers.image.base.name="docker.io/library/ubuntu:22.04"

            ### ARG declarations ###
            ARG DEBIAN_FRONTEND=noninteractive
            ARG IMAGE_VERSION="1.0.1"
            ARG BUILDARCH
            ARG TARGETARCH=${BUILDARCH}

            ### Install Apt Packages ###
            RUN echo 'Acquire::Retries "3"; Acquire::http::Timeout "30"; Acquire::https::Timeout "30";' > /etc/apt/apt.conf.d/99-retries && \\
                apt-get update -yqq --fix-missing && \\
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
                find . -type f -name '[rR]-4.5.1.*\\.(deb|rpm)' -delete

            # Install Quarto
            RUN --mount=type=secret,id=github_token,required=false bash -c "$(curl -1fsSL 'https://dl.posit.co/public/open/setup.deb.sh')" && \\
                apt-get install -yqq --no-install-recommends \\
                    quarto=1.8.27 \\
                    xz-utils && \\
                apt-mark hold quarto && \\
                apt-get clean -yqq && \\
                rm -rf /var/lib/apt/lists/* && \\
                GH_TOKEN="$([ -s /run/secrets/github_token ] && cat /run/secrets/github_token)" /opt/quarto/bin/quarto install tinytex --no-prompt
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

    def test_create_matrix(self, get_tmpcontext):
        """Test creating a new version in the BakeryConfig."""
        context = get_tmpcontext("barebones")
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1

        config.create_image("test-matrix")
        config.create_matrix(
            "test-matrix",
            dependency_constraints=[
                PythonDependencyConstraint(constraint={"latest": True, "count": 2}),
            ],
            dependencies=[
                RDependencyVersions(versions=["4.4.3", "4.3.3"]),
            ],
        )

        image = config.model.images[1]
        assert image.name == "test-matrix"
        assert image.matrix is not None
        expected_yaml = textwrap.indent(
            textwrap.dedent(f"""\
              matrix:
                dependencyConstraints:
                  - constraint:
                      count: 2
                      latest: true
                    dependency: python
                dependencies:
                  - versions:
                      - 4.4.3
                      - 4.3.3
                    dependency: R
        """),
            MATRIX_INDENT,
        )
        assert expected_yaml in (context / "bakery.yaml").read_text()
        assert (context / image.name / image.matrix.subpath).is_dir()
        assert (context / image.name / image.matrix.subpath / "Containerfile").is_file()
        assert (context / image.name / image.matrix.subpath / "deps").is_dir()
        assert (context / image.name / image.matrix.subpath / "deps" / "packages.txt").is_file()
        assert (context / image.name / image.matrix.subpath / "test").is_dir()
        assert (context / image.name / image.matrix.subpath / "test" / "goss.yaml").is_file()

    def test_create_matrix_image_does_not_exist(self, get_tmpcontext):
        """Test creating a new version in the BakeryConfig."""
        context = get_tmpcontext("barebones")
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1

        with pytest.raises(ValueError, match="Versions already exist for image 'scratch'"):
            config.create_matrix(
                "scratch",
                dependency_constraints=[
                    PythonDependencyConstraint(constraint={"latest": True, "count": 2}),
                ],
                dependencies=[
                    RDependencyVersions(versions=["4.4.3", "4.3.3"]),
                ],
            )

    def test_create_matrix_image_has_versions(self, get_tmpcontext):
        """Test creating a new version in the BakeryConfig."""
        context = get_tmpcontext("matrix")
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1

        with pytest.raises(ValueError, match="Image 'image-does-not-exist' does not exist in the config"):
            config.create_matrix(
                "image-does-not-exist",
                dependency_constraints=[
                    PythonDependencyConstraint(constraint={"latest": True, "count": 2}),
                ],
                dependencies=[
                    RDependencyVersions(versions=["4.4.3", "4.3.3"]),
                ],
            )

    def test_create_matrix_exists_no_force(self, get_tmpcontext):
        """Test creating a new version in the BakeryConfig."""
        context = get_tmpcontext("matrix")
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1

        with pytest.raises(
            ValueError, match="Cannot create matrix for image 'test-matrix' because it already defines a matrix."
        ):
            config.create_matrix(
                "test-matrix",
                dependency_constraints=[
                    PythonDependencyConstraint(constraint={"latest": True, "count": 2}),
                ],
                dependencies=[
                    RDependencyVersions(versions=["4.4.3", "4.3.3"]),
                ],
            )

        image = config.model.images[0]
        assert image.name == "test-matrix"
        assert image.matrix is not None
        expected_yaml = textwrap.indent(
            textwrap.dedent(f"""\
              matrix:
                dependencyConstraints:
                  - dependency: R
                    constraint:
                      count: 2
                      latest: true
                  - dependency: python
                    constraint:
                      count: 2
                      latest: true
                  - dependency: quarto
                    constraint:
                      latest: true
        """),
            MATRIX_INDENT,
        )
        assert expected_yaml in (context / "bakery.yaml").read_text()
        assert (context / image.name / image.matrix.subpath).is_dir()
        assert (context / image.name / image.matrix.subpath / "Containerfile.ubuntu2404").is_file()
        assert (context / image.name / image.matrix.subpath / "deps").is_dir()
        assert (context / image.name / image.matrix.subpath / "deps" / "ubuntu-24.04_packages.txt").is_file()
        assert (context / image.name / image.matrix.subpath / "test").is_dir()
        assert (context / image.name / image.matrix.subpath / "test" / "goss.yaml").is_file()

    def test_create_matrix_exists_force(self, get_tmpcontext):
        """Test creating a new version in the BakeryConfig."""
        context = get_tmpcontext("matrix")
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1

        config.create_matrix(
            "test-matrix",
            dependency_constraints=[
                PythonDependencyConstraint(constraint={"latest": True, "count": 2}),
            ],
            dependencies=[
                RDependencyVersions(versions=["4.4.3", "4.3.3"]),
            ],
            subpath="matrix-override",
            force=True,
        )

        image = config.model.images[0]
        assert image.name == "test-matrix"
        assert image.matrix is not None
        assert image.matrix.subpath == "matrix-override"
        expected_yaml = textwrap.indent(
            textwrap.dedent(f"""\
              matrix:
                subpath: matrix-override
                dependencyConstraints:
                  - constraint:
                      count: 2
                      latest: true
                    dependency: python
                dependencies:
                  - versions:
                      - 4.4.3
                      - 4.3.3
                    dependency: R
        """),
            MATRIX_INDENT,
        )
        assert expected_yaml in (context / "bakery.yaml").read_text()
        assert (context / image.name / image.matrix.subpath).is_dir()
        assert (context / image.name / image.matrix.subpath / f"Containerfile.ubuntu2404").is_file()
        assert (context / image.name / image.matrix.subpath / "deps").is_dir()
        assert (context / image.name / image.matrix.subpath / "deps" / "ubuntu-24.04_packages.txt").is_file()
        assert (context / image.name / image.matrix.subpath / "test").is_dir()
        assert (context / image.name / image.matrix.subpath / "test" / "goss.yaml").is_file()

    def test_rerender_files_whole_version(self, get_context, get_tmpcontext):
        """Test regenerating files for an existing version with no directory in the BakeryConfig."""
        context = get_tmpcontext("basic")
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert len(image.versions) == 1
        version = image.versions[0]

        shutil.rmtree(version.path)
        assert not version.path.exists()

        config.rerender_files()

        assert version.path.exists()
        assert_directories_match(version.path, get_context("basic") / image.name / version.name)

    def test_rerender_files_matrix(self, get_context, get_tmpcontext):
        """Test regenerating files for an existing version with no directory in the BakeryConfig."""
        context = get_tmpcontext("matrix")
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert image.matrix is not None
        matrix = image.matrix

        shutil.rmtree(matrix.path)
        assert not matrix.path.exists()

        config.rerender_files()

        assert matrix.path.exists()
        assert_directories_match(matrix.path, get_context("matrix") / image.name / matrix.subpath)

    def test_rerender_files_altered_file(self, get_context, get_tmpcontext):
        """Test regenerating files for an existing version with no directory in the BakeryConfig."""
        context = get_tmpcontext("basic")
        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert len(image.versions) == 1
        version = image.versions[0]

        # Modify a file to ensure it gets overwritten
        (version.path / "Containerfile.ubuntu2204.min").write_text("This is an altered file.")
        assert "This is an altered file." in (version.path / "Containerfile.ubuntu2204.min").read_text()

        config.rerender_files()

        assert version.path.exists()
        assert_directories_match(version.path, get_context("basic") / image.name / version.name)

    def test_rerender_files_with_filter(self, get_tmpcontext):
        """Test regenerating files for an existing version with no directory in the BakeryConfig."""
        context = get_tmpcontext("basic")

        # Filter on a non-existent version. It won't cause an error, and it won't recreate the directory we changed.
        _filter = BakeryConfigFilter(image_name="test-image", image_version="2.0.0")

        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert len(image.versions) == 1
        version = image.versions[0]

        shutil.rmtree(version.path)
        assert not version.path.exists()

        config.rerender_files(_filter)

        assert not version.path.exists()

    def test_rerender_files_with_regex(self, get_context, get_tmpcontext):
        """Test regenerating files for an existing version with no directory in the BakeryConfig."""
        context = get_tmpcontext("basic")

        config = BakeryConfig.from_context(context)
        assert len(config.model.images) == 1
        image = config.model.images[0]
        assert len(image.versions) == 1
        version = image.versions[0]

        shutil.rmtree(version.path)
        assert not version.path.exists()

        config.rerender_files(regex_filters=[r"deps"])

        assert version.path.exists()
        assert_directories_match(version.path / "deps", get_context("basic") / image.name / version.name / "deps")
        # Non-matching files should not be rendered
        assert not (version.path / "Containerfile.ubuntu2204.std").exists()
        assert not (version.path / "Containerfile.ubuntu2204.min").exists()
        assert not (version.path / "test").exists()

    def test_target_generation_matrix(self, get_tmpcontext):
        config = BakeryConfig(
            get_tmpcontext("matrix") / "bakery.yaml",
            settings=BakerySettings(matrix_versions=MatrixVersionInclusionEnum.INCLUDE),
        )
        assert len(config.targets) == 4

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

    def test_target_filtering_filter_platform(self, testdata_path):
        complex_yaml = testdata_path / "valid" / "complex.yaml"

        settings = BakerySettings(filter=BakeryConfigFilter(image_platform=["linux/arm64"]))
        config = BakeryConfig(complex_yaml, settings)
        assert len(config.targets) == 2

        settings = BakerySettings(filter=BakeryConfigFilter(image_platform=["linux/amd64"]))
        config = BakeryConfig(complex_yaml, settings)
        assert len(config.targets) == 10

        settings = BakerySettings(filter=BakeryConfigFilter(image_platform=["linux/amd64", "linux/arm64"]))
        config = BakeryConfig(complex_yaml, settings)
        assert len(config.targets) == 10

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

    def test__merge_sequential_build_metadata_files(self, get_config_obj):
        """Test merging sequential build metadata files."""
        config = get_config_obj("basic")
        for target in config.targets:
            metadata_filepath = CONFIG_TESTDATA_DIR / "build_metadata" / f"{target.uid}.json"
            target.build_metadata.append(BuildMetadata.model_validate_json(metadata_filepath.read_text()))

        merged_metadata = config._merge_sequential_build_metadata_files()
        with open(CONFIG_TESTDATA_DIR / "build_metadata" / "expected.json", "r") as f:
            expected_metadata = json.load(f)

        assert merged_metadata == expected_metadata

    def test_load_build_metadata_file(self, get_config_obj):
        """Test loading a build metadata file."""
        metadata_filepath = CONFIG_TESTDATA_DIR / "build_metadata" / "expected.json"
        config = get_config_obj("basic")
        config.load_build_metadata_from_file(metadata_filepath)

        for target in config.targets:
            assert len(target.build_metadata) == 1
            assert target.build_metadata[0] is not None
            assert target.build_metadata[0].image_name is not None
            assert target.build_metadata[0].container_image_digest is not None

    def test_generate_image_targets_rejects_duplicate_uid(self, get_config_obj):
        """Two targets sharing a UID fail fast instead of silently colliding.

        Build metadata is keyed by UID, so a duplicate UID would let one build's
        metadata match another target and push to the wrong registries. This is a
        defense-in-depth guard for the posit-dev/images-shared#553 collision class.
        """
        config = get_config_obj("basic")
        image = config.model.get_image("test-image")
        version = image.get_version("1.0.0")
        clone = version.model_copy(deep=True)
        clone.parent = version.parent
        image.versions.append(clone)

        with pytest.raises(BakeryError, match="Duplicate image target UID"):
            config.generate_image_targets()

    def test_dev_and_release_same_version_do_not_collide(self, get_config_obj):
        """A dev-stream version and a release version of the same number coexist with
        distinct UIDs and generate without error."""
        config = get_config_obj("basic")
        image = config.model.get_image("test-image")
        release = image.get_version("1.0.0")

        dev = release.model_copy(deep=True)
        dev.parent = release.parent
        dev.isDevelopmentVersion = True
        dev.metadata = {"release_channel": ReleaseChannelEnum.DAILY}
        image.versions.append(dev)

        config.generate_image_targets(BakerySettings(dev_versions=DevVersionInclusionEnum.INCLUDE))

        uids = [t.uid for t in config.targets if t.image_version.name == "1.0.0"]
        assert len(uids) == len(set(uids))
        assert any(u.endswith("-daily") for u in uids)
        assert any(not u.endswith("-daily") for u in uids)

    @pytest.mark.parametrize(
        "untagged,older_than_days,expected_deletions",
        [
            pytest.param(
                False,
                None,
                [],
                id="no-untagged-no-older-than-days-no-deletions",
            ),
            pytest.param(
                True,
                None,
                [565937362, 565937363],
                id="untagged-no-older-than-days-deletions",
            ),
            pytest.param(
                False,
                14,
                [565937361, 565937362],
                id="no-untagged-older-than-days-deletions",
            ),
            pytest.param(
                True,
                14,
                [565937361, 565937362, 565937363],
                id="untagged-older-than-days-deletions",
            ),
        ],
    )
    def test_clean_caches(
        self,
        mocker,
        get_tmpcontext,
        cache_ghcr_package_versions_data,
        untagged,
        older_than_days,
        expected_deletions,
    ):
        """Test cleaning caches in the BakeryConfig."""
        context = get_tmpcontext("basic")
        cache_registry = "ghcr.io/posit-test"
        settings = BakerySettings(cache_registry=cache_registry)
        config = BakeryConfig.from_context(context, settings)

        mock_ghcr_client = mocker.patch("posit_bakery.registry_management.ghcr.clean.GHCRClient")
        mock_ghcr_client_instance = mock_ghcr_client.return_value
        mock_ghcr_client_instance.get_package_versions.return_value = cache_ghcr_package_versions_data

        # Clean caches
        config.clean_caches(
            remove_untagged=untagged,
            remove_older_than=timedelta(days=older_than_days) if older_than_days is not None else None,
        )

        mock_ghcr_client.assert_called_once()
        mock_ghcr_client_instance.get_package_versions.assert_called_once()
        if expected_deletions:
            versions_deleted = mock_ghcr_client_instance.delete_package_versions.call_args.args[0]
            assert len(versions_deleted.versions) == len(expected_deletions)
            for version_id in expected_deletions:
                assert version_id in [v.id for v in versions_deleted.versions]
        else:
            mock_ghcr_client_instance.delete_package_version.assert_not_called()

    def test_clean_caches_dry_run(
        self,
        mocker,
        get_tmpcontext,
        cache_ghcr_package_versions_data,
    ):
        """Test cleaning caches in the BakeryConfig."""
        context = get_tmpcontext("basic")
        cache_registry = "ghcr.io/posit-test"
        settings = BakerySettings(cache_registry=cache_registry)
        config = BakeryConfig.from_context(context, settings)

        mock_ghcr_client = mocker.patch("posit_bakery.registry_management.ghcr.clean.GHCRClient")
        mock_ghcr_client_instance = mock_ghcr_client.return_value
        mock_ghcr_client_instance.get_package_versions.return_value = cache_ghcr_package_versions_data

        # Clean caches
        config.clean_caches(
            remove_untagged=True,
            remove_older_than=timedelta(days=14),
            dry_run=True,
        )

        mock_ghcr_client.assert_called_once()
        mock_ghcr_client_instance.get_package_versions.assert_called_once()
        mock_ghcr_client_instance.delete_package_version.assert_not_called()

    @pytest.mark.parametrize(
        "untagged,older_than_days,expected_deletions",
        [
            pytest.param(
                False,
                None,
                [],
                id="no-untagged-no-older-than-days-no-deletions",
            ),
            pytest.param(
                True,
                None,
                [565937359, 565937360, 565937361, 565937362, 565937363],
                id="untagged-no-older-than-days-deletions",
            ),
            pytest.param(
                False,
                14,
                [565937361, 565937362],
                id="no-untagged-older-than-days-deletions",
            ),
            pytest.param(
                True,
                14,
                [565937359, 565937360, 565937361, 565937362, 565937363],
                id="untagged-older-than-days-deletions",
            ),
        ],
    )
    def test_clean_temporary(
        self,
        mocker,
        get_tmpcontext,
        temp_ghcr_package_versions_data,
        untagged,
        older_than_days,
        expected_deletions,
    ):
        """Test cleaning temporary images in the BakeryConfig."""
        context = get_tmpcontext("basic")
        temp_registry = "ghcr.io/posit-test"
        settings = BakerySettings(temp_registry=temp_registry)
        config = BakeryConfig.from_context(context, settings)

        mock_ghcr_client = mocker.patch("posit_bakery.registry_management.ghcr.clean.GHCRClient")
        mock_ghcr_client_instance = mock_ghcr_client.return_value
        mock_ghcr_client_instance.get_package_versions.return_value = temp_ghcr_package_versions_data

        # Clean temp images
        config.clean_temporary(
            remove_untagged=untagged,
            remove_older_than=timedelta(days=older_than_days) if older_than_days is not None else None,
        )

        mock_ghcr_client.assert_called_once()
        mock_ghcr_client_instance.get_package_versions.assert_called_once()
        if expected_deletions:
            versions_deleted = mock_ghcr_client_instance.delete_package_versions.call_args.args[0]
            assert len(versions_deleted.versions) == len(expected_deletions)
            for version_id in expected_deletions:
                assert version_id in [v.id for v in versions_deleted.versions]
        else:
            mock_ghcr_client_instance.delete_package_version.assert_not_called()

    def test_clean_temporary_dry_run(
        self,
        mocker,
        get_tmpcontext,
        temp_ghcr_package_versions_data,
    ):
        """Test cleaning temp images in the BakeryConfig."""
        context = get_tmpcontext("basic")
        temp_registry = "ghcr.io/posit-test"
        settings = BakerySettings(temp_registry=temp_registry)
        config = BakeryConfig.from_context(context, settings)

        mock_ghcr_client = mocker.patch("posit_bakery.registry_management.ghcr.clean.GHCRClient")
        mock_ghcr_client_instance = mock_ghcr_client.return_value
        mock_ghcr_client_instance.get_package_versions.return_value = temp_ghcr_package_versions_data

        # Clean temp images
        config.clean_temporary(
            remove_untagged=True,
            remove_older_than=timedelta(days=14),
            dry_run=True,
        )

        mock_ghcr_client.assert_called_once()
        mock_ghcr_client_instance.get_package_versions.assert_called_once()
        mock_ghcr_client_instance.delete_package_version.assert_not_called()


class TestApplyDevSpecReleaseBranch:
    """release_branch is set from YYYY.MM when version is set, or directly from spec."""

    def _make_image(self, tmp_path):
        """Return a minimal Image with one workbench daily dev version."""
        doc = BakeryConfigDocument(
            base_path=tmp_path,
            **{
                "repository": {"url": "https://github.com/posit-dev/test"},
                "images": [
                    {
                        "name": "test-image",
                        "devVersions": [
                            {
                                "sourceType": "stream",
                                "product": "workbench",
                                "channel": "daily",
                                "os": [{"name": "Ubuntu 24.04", "primary": True}],
                            }
                        ],
                    }
                ],
            },
        )
        return doc.images[0]

    def test_version_sets_calver_release_branch(self, tmp_path):
        """version in DevBuildSpec pins version and derives YYYY.MM release_branch."""
        image = self._make_image(tmp_path)
        spec = DevBuildSpec(version="2026.06.0-daily+143-gABC")
        settings = BakerySettings(
            dev_versions=DevVersionInclusionEnum.ONLY,
            dev_spec=spec,
        )
        _apply_dev_spec(image, settings)
        dv = image.devVersions[0]
        assert dv.version_override == "2026.06.0-daily+143-gABC"
        assert dv.release_branch == "2026.06"

    def test_release_branch_only_sets_branch(self, tmp_path):
        """release_branch in DevBuildSpec sets release_branch directly; version_override stays None."""
        image = self._make_image(tmp_path)
        spec = DevBuildSpec(release_branch="apple-blossom")
        settings = BakerySettings(
            dev_versions=DevVersionInclusionEnum.ONLY,
            dev_spec=spec,
        )
        _apply_dev_spec(image, settings)
        dv = image.devVersions[0]
        assert dv.version_override is None
        assert dv.release_branch == "apple-blossom"

    def test_version_takes_precedence_over_release_branch(self, tmp_path):
        """When both are set, version wins; release_branch is YYYY.MM, not spec.release_branch."""
        image = self._make_image(tmp_path)
        spec = DevBuildSpec(version="2026.06.0-daily+143-gABC", release_branch="apple-blossom")
        settings = BakerySettings(
            dev_versions=DevVersionInclusionEnum.ONLY,
            dev_spec=spec,
        )
        _apply_dev_spec(image, settings)
        dv = image.devVersions[0]
        assert dv.version_override == "2026.06.0-daily+143-gABC"
        assert dv.release_branch == "2026.06"

    def test_extract_calver_minor_rejects_trailing_garbage(self):
        with pytest.raises(ValueError, match="not a valid CalVer"):
            _extract_calver_minor("2026.06.0-daily+143 trailing garbage")


class TestApplyDevSpecDependency:
    """--dev-spec pins dependency-sourced dev versions, matched by channel."""

    def _make_image(self, tmp_path, *, channel="daily", extra_dev_versions=None):
        """Return a minimal Image with one positron daily dependency dev version."""
        dev_version = {
            "sourceType": "dependency",
            "dependency": "positron",
            "prerelease": True,
            "channel": channel,
            "os": [{"name": "Ubuntu 24.04", "primary": True}],
        }
        doc = BakeryConfigDocument(
            base_path=tmp_path,
            **{
                "repository": {"url": "https://github.com/posit-dev/test"},
                "images": [
                    {
                        "name": "test-positron-init",
                        "devVersions": [dev_version, *(extra_dev_versions or [])],
                    }
                ],
            },
        )
        return doc.images[0]

    def test_version_pins_dependency_dev_version(self, tmp_path):
        """version in DevBuildSpec sets version_override on the matching dependency dev version."""
        image = self._make_image(tmp_path)
        spec = DevBuildSpec(version="2026.06.0-99", channel="daily")
        settings = BakerySettings(dev_versions=DevVersionInclusionEnum.ONLY, dev_spec=spec)
        _apply_dev_spec(image, settings)
        assert image.devVersions[0].version_override == "2026.06.0-99"

    def test_channel_mismatch_is_noop(self, tmp_path):
        """A dev-spec channel that matches no dev version leaves version_override unset."""
        image = self._make_image(tmp_path, channel="daily")
        spec = DevBuildSpec(version="2026.06.0-99", channel="preview")
        settings = BakerySettings(dev_versions=DevVersionInclusionEnum.ONLY, dev_spec=spec)
        _apply_dev_spec(image, settings)
        assert image.devVersions[0].version_override is None

    def test_release_branch_ignored_for_dependency(self, tmp_path):
        """release_branch is not applicable to dependency dev versions and is not set."""
        image = self._make_image(tmp_path)
        spec = DevBuildSpec(version="2026.06.0-99", channel="daily", release_branch="apple-blossom")
        settings = BakerySettings(dev_versions=DevVersionInclusionEnum.ONLY, dev_spec=spec)
        _apply_dev_spec(image, settings)
        dv = image.devVersions[0]
        assert dv.version_override == "2026.06.0-99"
        assert not hasattr(dv, "release_branch")

    def test_branch_only_spec_skips_dependency_with_warning(self, tmp_path, caplog):
        """A branch-only spec cannot pin a dependency dev version: warns, leaves override None."""
        import logging

        image = self._make_image(tmp_path)
        spec = DevBuildSpec(release_branch="apple-blossom")
        settings = BakerySettings(dev_versions=DevVersionInclusionEnum.ONLY, dev_spec=spec)
        with caplog.at_level(logging.WARNING):
            _apply_dev_spec(image, settings)
        assert image.devVersions[0].version_override is None
        assert "cannot pin a dependency-sourced dev version" in caplog.text

    def test_ambiguous_candidates_raise(self, tmp_path):
        """Two dev versions matching the same channel raise a disambiguation error."""
        extra = {
            "sourceType": "stream",
            "product": "workbench",
            "channel": "daily",
            "os": [{"name": "Ubuntu 24.04", "primary": True}],
        }
        image = self._make_image(tmp_path, channel="daily", extra_dev_versions=[extra])
        spec = DevBuildSpec(version="2026.06.0-99", channel="daily")
        settings = BakerySettings(dev_versions=DevVersionInclusionEnum.ONLY, dev_spec=spec)
        with pytest.raises(ValueError, match="dev versions matching"):
            _apply_dev_spec(image, settings)
