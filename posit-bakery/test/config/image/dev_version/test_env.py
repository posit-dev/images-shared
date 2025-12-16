import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from posit_bakery.config import Image, BaseRegistry
from posit_bakery.config.image.dev_version import ImageDevelopmentVersionFromEnv
from posit_bakery.config.image.dev_version.env import _get_value_from_env

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


class TestGetValueFromEnv:
    def test_field_not_set(self):
        """Test that a ValueError is raised if the field is not set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="fieldEnvVar must be set."):
                _get_value_from_env("fieldEnvVar", None)

    def test_env_var_unset(self):
        """Test that a ValueError is raised if the environment variable is not set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Environment variable 'UNSET_ENV_VAR' is not set."):
                _get_value_from_env("fieldEnvVar", "UNSET_ENV_VAR")

    def test_env_var_set(self):
        """Test that a ValueError is raised if the environment variable is not set."""
        with patch.dict(os.environ, {"SET_ENV_VAR": "value"}, clear=True):
            result = _get_value_from_env("fieldEnvVar", "SET_ENV_VAR")
            assert result == "value"


class TestImageDevelopmentVersionFromEnv:
    def test_name_required(self):
        """Test that an ImageDevelopmentVersionFromEnv object requires a name."""
        with pytest.raises(ValidationError, match="Field required"):
            ImageDevelopmentVersionFromEnv()

    @patch.dict("os.environ", {}, clear=True)
    def test_unset_env_vars(self):
        """Test creating an ImageDevelopmentVersionFromEnv object with only the name does not raise an exception.

        Test that the default values for subpath, latest, registries, and os are set correctly.
        """
        with pytest.raises(ValidationError, match="is not set"):
            ImageDevelopmentVersionFromEnv(
                sourceType="env",
                versionEnvVar="VERSION_ENV_VAR",
                urlEnvVar="URL_ENV_VAR",
            )

    def test_valid(self):
        """Test creating a valid ImageDevelopmentVersionFromEnv object with all fields.

        Test that ImageDevelopmentVersionFromEnv objects are correctly initialized and parented.
        """
        env_version = "1.0.0"
        env_url = "https://example.com/image.tar.gz"
        with patch.dict(os.environ, {"VERSION_ENV_VAR": env_version, "URL_ENV_VAR": env_url}, clear=True):
            i = ImageDevelopmentVersionFromEnv(
                sourceType="env",
                versionEnvVar="VERSION_ENV_VAR",
                urlEnvVar="URL_ENV_VAR",
                extraRegistries=[
                    {"host": "registry1.example.com", "namespace": "namespace1"},
                    {"host": "registry2.example.com", "namespace": "namespace2"},
                ],
                os=[{"name": "Ubuntu 22.04", "primary": True}, {"name": "Ubuntu 24.04"}],
            )

            assert len(i.all_registries) == 2
            assert len(i.os) == 2
            for _os in i.os:
                assert _os.parent is i
            assert i.get_version() == env_version
            assert all(url == env_url for url in i.get_url_by_os().values())

    def test_deduplicate_registries(self, caplog):
        """Test that duplicate registries are deduplicated."""
        env_version = "1.0.0"
        env_url = "https://example.com/image.tar.gz"
        with patch.dict(os.environ, {"VERSION_ENV_VAR": env_version, "URL_ENV_VAR": env_url}, clear=True):
            i = ImageDevelopmentVersionFromEnv(
                sourceType="env",
                versionEnvVar="VERSION_ENV_VAR",
                urlEnvVar="URL_ENV_VAR",
                extraRegistries=[
                    {"host": "registry1.example.com", "namespace": "namespace1"},
                    {"host": "registry1.example.com", "namespace": "namespace1"},  # Duplicate
                ],
            )

        assert len(i.all_registries) == 1
        assert i.all_registries[0].host == "registry1.example.com"
        assert i.all_registries[0].namespace == "namespace1"
        assert "WARNING" in caplog.text
        assert (
            "Duplicate registry defined in config for image development version: "
            "registry1.example.com/namespace1" in caplog.text
        )

    def test_check_os_not_empty(self, caplog):
        """Test that an BaseImageDevelopmentVersion must have at least one OS defined."""
        env_version = "1.0.0"
        env_url = "https://example.com/image.tar.gz"
        with patch.dict(os.environ, {"VERSION_ENV_VAR": env_version, "URL_ENV_VAR": env_url}, clear=True):
            ImageDevelopmentVersionFromEnv(
                sourceType="env", versionEnvVar="VERSION_ENV_VAR", urlEnvVar="URL_ENV_VAR", os=[]
            )

        assert "WARNING" in caplog.text
        assert "No OSes defined for image development version." in caplog.text

    def test_deduplicate_os(self, caplog):
        """Test that duplicate OSes are deduplicated."""
        mock_parent = MagicMock(spec=Image)
        mock_parent.path = Path("/tmp/path")
        env_version = "1.0.0"
        env_url = "https://example.com/image.tar.gz"
        with patch.dict(os.environ, {"VERSION_ENV_VAR": env_version, "URL_ENV_VAR": env_url}, clear=True):
            i = ImageDevelopmentVersionFromEnv(
                parent=mock_parent,
                sourceType="env",
                versionEnvVar="VERSION_ENV_VAR",
                urlEnvVar="URL_ENV_VAR",
                os=[
                    {"name": "Ubuntu 22.04", "primary": True},
                    {"name": "Ubuntu 22.04"},  # Duplicate
                ],
            )
        assert len(i.os) == 1
        assert i.os[0].name == "Ubuntu 22.04"
        assert "WARNING" in caplog.text
        assert "Duplicate OS defined in config for image development version: Ubuntu 22.04" in caplog.text

    def test_make_single_os_primary(self, caplog):
        """Test that if only one OS is defined, it is automatically made primary."""
        env_version = "1.0.0"
        env_url = "https://example.com/image.tar.gz"
        with patch.dict(os.environ, {"VERSION_ENV_VAR": env_version, "URL_ENV_VAR": env_url}, clear=True):
            i = ImageDevelopmentVersionFromEnv(
                sourceType="env",
                versionEnvVar="VERSION_ENV_VAR",
                urlEnvVar="URL_ENV_VAR",
                os=[{"name": "Ubuntu 22.04"}],
            )
        assert len(i.os) == 1
        assert i.os[0].primary is True
        assert i.os[0].name == "Ubuntu 22.04"
        assert "WARNING" not in caplog.text

    def test_max_one_primary_os(self):
        """Test that an error is raised if multiple primary OSes are defined."""
        env_version = "1.0.0"
        env_url = "https://example.com/image.tar.gz"
        with pytest.raises(
            ValidationError,
            match="Only one OS can be marked as primary for image development version. Found 2 OSes marked primary.",
        ):
            with patch.dict(os.environ, {"VERSION_ENV_VAR": env_version, "URL_ENV_VAR": env_url}, clear=True):
                ImageDevelopmentVersionFromEnv(
                    sourceType="env",
                    versionEnvVar="VERSION_ENV_VAR",
                    urlEnvVar="URL_ENV_VAR",
                    os=[
                        {"name": "Ubuntu 22.04", "primary": True},
                        {"name": "Ubuntu 24.04", "primary": True},  # Multiple primary OSes
                    ],
                )

    def test_no_primary_os_warning(self, caplog):
        """Test that a warning is logged if no primary OS is defined."""
        env_version = "1.0.0"
        env_url = "https://example.com/image.tar.gz"
        with patch.dict(os.environ, {"VERSION_ENV_VAR": env_version, "URL_ENV_VAR": env_url}, clear=True):
            ImageDevelopmentVersionFromEnv(
                sourceType="env",
                versionEnvVar="VERSION_ENV_VAR",
                urlEnvVar="URL_ENV_VAR",
                os=[{"name": "Ubuntu 22.04"}, {"name": "Ubuntu 24.04"}],
            )

        assert "WARNING" in caplog.text
        assert "No OS marked as primary for image development version." in caplog.text

    def test_extra_registries_or_override_registries(self):
        """Test that only one of extraRegistries or overrideRegistries can be defined."""
        env_version = "1.0.0"
        env_url = "https://example.com/image.tar.gz"
        with pytest.raises(
            ValidationError,
            match="Only one of 'extraRegistries' or 'overrideRegistries' can be defined for image development version.",
        ):
            with patch.dict(os.environ, {"VERSION_ENV_VAR": env_version, "URL_ENV_VAR": env_url}, clear=True):
                i = ImageDevelopmentVersionFromEnv(
                    sourceType="env",
                    versionEnvVar="VERSION_ENV_VAR",
                    urlEnvVar="URL_ENV_VAR",
                    extraRegistries=[{"host": "registry.example.com", "namespace": "namespace"}],
                    overrideRegistries=[{"host": "another.registry.com", "namespace": "another_namespace"}],
                )

    def test_all_registries(self):
        """Test that merged_registries returns the correct list of registries for object and parents."""
        expected_registries = [
            BaseRegistry(host="docker.io", namespace="posit"),
            BaseRegistry(host="ghcr.io", namespace="posit-dev"),
            BaseRegistry(host="ghcr.io", namespace="posit-team"),
            BaseRegistry(host="registry1.example.com", namespace="namespace1"),
        ]

        mock_image_parent = MagicMock(spec=Image)
        mock_image_parent.all_registries = [
            expected_registries[0],  # docker.io/posit
            expected_registries[1],  # ghcr.io/posit-dev
            expected_registries[2],  # ghcr.io/posit-team
        ]

        env_version = "1.0.0"
        env_url = "https://example.com/image.tar.gz"
        with patch.dict(os.environ, {"VERSION_ENV_VAR": env_version, "URL_ENV_VAR": env_url}, clear=True):
            i = ImageDevelopmentVersionFromEnv(
                parent=mock_image_parent,
                sourceType="env",
                versionEnvVar="VERSION_ENV_VAR",
                urlEnvVar="URL_ENV_VAR",
                extraRegistries=[
                    expected_registries[3],  # registry1.example.com/namespace1
                    expected_registries[0],  # docker.io/posit
                ],
            )

        assert len(i.all_registries) == 4
        for registry in expected_registries:
            assert registry in i.all_registries

    def test_all_registries_with_override(self):
        """Test that merged_registries returns the correct list of registries when overridden."""
        parent_registries = [
            BaseRegistry(host="docker.io", namespace="posit"),
            BaseRegistry(host="ghcr.io", namespace="posit-dev"),
            BaseRegistry(host="ghcr.io", namespace="posit-team"),
        ]
        override_registries = [
            BaseRegistry(host="ghcr.io", namespace="posit-team"),
            BaseRegistry(host="registry1.example.com", namespace="namespace1"),
        ]

        mock_image_parent = MagicMock(spec=Image)
        mock_image_parent.merged_registries = parent_registries

        env_version = "1.0.0"
        env_url = "https://example.com/image.tar.gz"
        with patch.dict(os.environ, {"VERSION_ENV_VAR": env_version, "URL_ENV_VAR": env_url}, clear=True):
            i = ImageDevelopmentVersionFromEnv(
                parent=mock_image_parent,
                sourceType="env",
                versionEnvVar="VERSION_ENV_VAR",
                urlEnvVar="URL_ENV_VAR",
                overrideRegistries=override_registries,
            )

        assert len(i.all_registries) == 2
        for registry in override_registries:
            assert registry in i.all_registries
