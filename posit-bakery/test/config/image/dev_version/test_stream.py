import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from posit_bakery.config import Image, Registry, ImageVersionOS
from posit_bakery.config.image import SUPPORTED_OS, BuildOS
from posit_bakery.config.image.dev_version import ImageDevelopmentVersionFromProductStream
from posit_bakery.config.image.posit_product.const import ProductEnum, ReleaseStreamEnum
from posit_bakery.config.image.posit_product.main import ReleaseStreamResult

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


class TestImageDevelopmentVersionFromProductStream:
    def test_name_required(self):
        """Test that an ImageDevelopmentVersionFromEnv object requires a name."""
        with pytest.raises(ValidationError, match="Field required"):
            ImageDevelopmentVersionFromProductStream()

    def test_bad_product(self):
        """Test that an ImageDevelopmentVersionFromEnv object requires a valid product."""
        with pytest.raises(ValidationError, match="Input should be"):
            ImageDevelopmentVersionFromProductStream(
                sourceType="stream",
                product="invalid_product",
                stream="daily",
            )

    def test_bad_stream(self):
        """Test that an ImageDevelopmentVersionFromEnv object requires a valid stream."""
        with pytest.raises(ValidationError, match="Input should be"):
            ImageDevelopmentVersionFromProductStream(
                sourceType="stream",
                product="workbench",
                stream="invalid_stream",
            )

    def test_valid(self):
        """Test creating a valid ImageDevelopmentVersionFromEnv object with all fields.

        Test that ImageDevelopmentVersionFromEnv objects are correctly initialized and parented.
        """
        with patch("posit_bakery.config.image.dev_version.stream.get_product_artifact_by_stream") as mock_get:
            mock_get.return_value = ReleaseStreamResult(
                version="1.0.0", download_url="https://example.com/image.tar.gz"
            )
            i = ImageDevelopmentVersionFromProductStream(
                sourceType="stream",
                product="workbench",
                stream="daily",
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
            assert i.get_version() == mock_get.return_value.version
            assert all(url == str(mock_get.return_value.download_url) for url in i.get_url_by_os().values())

    def test_deduplicate_registries(self, caplog):
        """Test that duplicate registries are deduplicated."""
        with patch("posit_bakery.config.image.dev_version.stream.get_product_artifact_by_stream") as mock_get:
            mock_get.return_value = ReleaseStreamResult(
                version="1.0.0", download_url="https://example.com/image.tar.gz"
            )
            i = ImageDevelopmentVersionFromProductStream(
                sourceType="stream",
                product="workbench",
                stream="daily",
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
        with patch("posit_bakery.config.image.dev_version.stream.get_product_artifact_by_stream") as mock_get:
            mock_get.return_value = ReleaseStreamResult(
                version="1.0.0", download_url="https://example.com/image.tar.gz"
            )
            i = ImageDevelopmentVersionFromProductStream(
                sourceType="stream", product="workbench", stream="daily", os=[]
            )

        assert "WARNING" in caplog.text
        assert (
            "No OSes defined for image development version. At least one OS should be defined "
            "for complete tagging and labeling of images." in caplog.text
        )

    def test_deduplicate_os(self, caplog):
        """Test that duplicate OSes are deduplicated."""
        mock_parent = MagicMock(spec=Image)
        mock_parent.path = Path("/tmp/path")
        with patch("posit_bakery.config.image.dev_version.stream.get_product_artifact_by_stream") as mock_get:
            mock_get.return_value = ReleaseStreamResult(
                version="1.0.0", download_url="https://example.com/image.tar.gz"
            )
            i = ImageDevelopmentVersionFromProductStream(
                parent=mock_parent,
                sourceType="stream",
                product="workbench",
                stream="daily",
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
        with patch("posit_bakery.config.image.dev_version.stream.get_product_artifact_by_stream") as mock_get:
            mock_get.return_value = ReleaseStreamResult(
                version="1.0.0", download_url="https://example.com/image.tar.gz"
            )
            i = ImageDevelopmentVersionFromProductStream(
                sourceType="stream", product="workbench", stream="daily", os=[{"name": "Ubuntu 22.04"}]
            )

        assert len(i.os) == 1
        assert i.os[0].primary is True
        assert i.os[0].name == "Ubuntu 22.04"
        assert (
            "No primary OS defined for image version. At least one OS should be marked as "
            "primary for complete tagging and labeling of images."
        ) not in caplog.text

    def test_max_one_primary_os(self):
        """Test that an error is raised if multiple primary OSes are defined."""
        with pytest.raises(
            ValidationError,
            match="Only one OS can be marked as primary for image development version. Found 2 OSes marked primary.",
        ):
            with patch("posit_bakery.config.image.dev_version.stream.get_product_artifact_by_stream") as mock_get:
                mock_get.return_value = ReleaseStreamResult(
                    version="1.0.0", download_url="https://example.com/image.tar.gz"
                )
                i = ImageDevelopmentVersionFromProductStream(
                    sourceType="stream",
                    product="workbench",
                    stream="daily",
                    os=[
                        {"name": "Ubuntu 22.04", "primary": True},
                        {"name": "Ubuntu 24.04", "primary": True},  # Multiple primary OSes
                    ],
                )

    def test_no_primary_os_warning(self, caplog):
        """Test that a warning is logged if no primary OS is defined."""
        with patch("posit_bakery.config.image.dev_version.stream.get_product_artifact_by_stream") as mock_get:
            mock_get.return_value = ReleaseStreamResult(
                version="1.0.0", download_url="https://example.com/image.tar.gz"
            )
            i = ImageDevelopmentVersionFromProductStream(
                sourceType="stream",
                product="workbench",
                stream="daily",
                os=[{"name": "Ubuntu 22.04"}, {"name": "Ubuntu 24.04"}],
            )

        assert "WARNING" in caplog.text
        assert (
            "No OS marked as primary for image development version. At least one OS should be "
            "marked as primary for complete tagging and labeling of images." in caplog.text
        )

    def test_extra_registries_or_override_registries(self):
        """Test that only one of extraRegistries or overrideRegistries can be defined."""
        with pytest.raises(
            ValidationError,
            match="Only one of 'extraRegistries' or 'overrideRegistries' can be defined for image development version.",
        ):
            with patch("posit_bakery.config.image.dev_version.stream.get_product_artifact_by_stream") as mock_get:
                mock_get.return_value = ReleaseStreamResult(
                    version="1.0.0", download_url="https://example.com/image.tar.gz"
                )
                i = ImageDevelopmentVersionFromProductStream(
                    sourceType="stream",
                    product="workbench",
                    stream="daily",
                    extraRegistries=[{"host": "registry.example.com", "namespace": "namespace"}],
                    overrideRegistries=[{"host": "another.registry.com", "namespace": "another_namespace"}],
                )

    def test_all_registries(self):
        """Test that merged_registries returns the correct list of registries for object and parents."""
        expected_registries = [
            Registry(host="docker.io", namespace="posit"),
            Registry(host="ghcr.io", namespace="posit-dev"),
            Registry(host="ghcr.io", namespace="posit-team"),
            Registry(host="registry1.example.com", namespace="namespace1"),
        ]

        mock_image_parent = MagicMock(spec=Image)
        mock_image_parent.all_registries = [
            expected_registries[0],  # docker.io/posit
            expected_registries[1],  # ghcr.io/posit-dev
            expected_registries[2],  # ghcr.io/posit-team
        ]

        with patch("posit_bakery.config.image.dev_version.stream.get_product_artifact_by_stream") as mock_get:
            mock_get.return_value = ReleaseStreamResult(
                version="1.0.0", download_url="https://example.com/image.tar.gz"
            )
            i = ImageDevelopmentVersionFromProductStream(
                parent=mock_image_parent,
                sourceType="stream",
                product="workbench",
                stream="daily",
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
            Registry(host="docker.io", namespace="posit"),
            Registry(host="ghcr.io", namespace="posit-dev"),
            Registry(host="ghcr.io", namespace="posit-team"),
        ]
        override_registries = [
            Registry(host="ghcr.io", namespace="posit-team"),
            Registry(host="registry1.example.com", namespace="namespace1"),
        ]

        mock_image_parent = MagicMock(spec=Image)
        mock_image_parent.merged_registries = parent_registries

        with patch("posit_bakery.config.image.dev_version.stream.get_product_artifact_by_stream") as mock_get:
            mock_get.return_value = ReleaseStreamResult(
                version="1.0.0", download_url="https://example.com/image.tar.gz"
            )
            i = ImageDevelopmentVersionFromProductStream(
                parent=mock_image_parent,
                sourceType="stream",
                product="workbench",
                stream="daily",
                overrideRegistries=override_registries,
            )

        assert len(i.all_registries) == 2
        for registry in override_registries:
            assert registry in i.all_registries


class TestByStream:
    @pytest.mark.parametrize(
        "_os,expected_version,expected_url",
        [
            pytest.param(
                ImageVersionOS(name="Debian 12"),
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect_2025.03.0~ubuntu24_amd64.deb",
                id="debian-12",
            ),
            pytest.param(
                ImageVersionOS(name="Debian 11"),
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect_2025.03.0~ubuntu22_amd64.deb",
                id="debian-11",
            ),
            pytest.param(
                ImageVersionOS(name="Ubuntu 24.04"),
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect_2025.03.0~ubuntu24_amd64.deb",
                id="ubuntu-24",
            ),
            pytest.param(
                ImageVersionOS(name="Ubuntu 22.04"),
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect_2025.03.0~ubuntu22_amd64.deb",
                id="ubuntu-22",
            ),
            pytest.param(
                ImageVersionOS(name="AlmaLinux 8"),
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect-2025.03.0.el8.x86_64.rpm",
                id="alma-8",
            ),
            pytest.param(
                ImageVersionOS(name="Rocky Linux 8"),
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect-2025.03.0.el8.x86_64.rpm",
                id="rocky-8",
            ),
            pytest.param(
                ImageVersionOS(name="RHEL 8"),
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect-2025.03.0.el8.x86_64.rpm",
                id="rhel-8",
            ),
            pytest.param(
                ImageVersionOS(name="AlmaLinux 9"),
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect-2025.03.0.el9.x86_64.rpm",
                id="alma-9",
            ),
            pytest.param(
                ImageVersionOS(name="Rocky Linux 9"),
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect-2025.03.0.el9.x86_64.rpm",
                id="rocky-9",
            ),
            pytest.param(
                ImageVersionOS(name="RHEL 9"),
                "2025.03.0",
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect-2025.03.0.el9.x86_64.rpm",
                id="rhel-9",
            ),
        ],
    )
    def test_connect_release(self, patch_requests_get, _os: ImageVersionOS, expected_version: str, expected_url: str):
        """Test that the correct URL is returned for a release version of Connect Release"""
        dev_version = ImageDevelopmentVersionFromProductStream(
            sourceType="stream", product=ProductEnum.CONNECT, stream=ReleaseStreamEnum.RELEASE, os=[_os]
        )
        assert dev_version.get_version() == expected_version
        assert dev_version.get_url_by_os()[_os.name] == expected_url
        assert str(_os.artifactDownloadURL) == expected_url

    @pytest.mark.parametrize(
        "_os,expected_version,expected_url",
        [
            pytest.param(
                ImageVersionOS(name="Debian 12"),
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/"
                "rstudio-connect_2025.04.0-dev%2B10-gbe0a4a3d31~ubuntu24_amd64.deb",
                id="debian-12",
            ),
            pytest.param(
                ImageVersionOS(name="Debian 11"),
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/"
                "rstudio-connect_2025.04.0-dev%2B10-gbe0a4a3d31~ubuntu22_amd64.deb",
                id="debian-11",
            ),
            pytest.param(
                ImageVersionOS(name="Ubuntu 24.04"),
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/rstudio-connect_2025.04.0-dev%2B10-gbe0a4a3d31~"
                "ubuntu24_amd64.deb",
                id="ubuntu-24",
            ),
            pytest.param(
                ImageVersionOS(name="Ubuntu 22.04"),
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/rstudio-connect_2025.04.0-dev%2B10-gbe0a4a3d31~"
                "ubuntu22_amd64.deb",
                id="ubuntu-22",
            ),
            pytest.param(
                ImageVersionOS(name="AlmaLinux 8"),
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/rstudio-connect-2025.04.0-dev%2B10-gbe0a4a3d31.el8.x86_64.rpm",
                id="alma-8",
            ),
            pytest.param(
                ImageVersionOS(name="Rocky Linux 8"),
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/rstudio-connect-2025.04.0-dev%2B10-gbe0a4a3d31.el8.x86_64.rpm",
                id="rocky-8",
            ),
            pytest.param(
                ImageVersionOS(name="RHEL 8"),
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/rstudio-connect-2025.04.0-dev%2B10-gbe0a4a3d31.el8.x86_64.rpm",
                id="rhel-8",
            ),
            pytest.param(
                ImageVersionOS(name="AlmaLinux 9"),
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/rstudio-connect-2025.04.0-dev%2B10-gbe0a4a3d31.el9.x86_64.rpm",
                id="alma-9",
            ),
            pytest.param(
                ImageVersionOS(name="Rocky Linux 9"),
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/rstudio-connect-2025.04.0-dev%2B10-gbe0a4a3d31.el9.x86_64.rpm",
                id="rocky-9",
            ),
            pytest.param(
                ImageVersionOS(name="RHEL 9"),
                "2025.04.0-dev+10-gbe0a4a3d31",
                "https://cdn.posit.co/connect/2025.04/rstudio-connect-2025.04.0-dev%2B10-gbe0a4a3d31.el9.x86_64.rpm",
                id="rhel-9",
            ),
        ],
    )
    def test_connect_daily(self, patch_requests_get, _os: ImageVersionOS, expected_version: str, expected_url: str):
        """Test that the correct URL is returned for a release version of Connect Daily"""
        dev_version = ImageDevelopmentVersionFromProductStream(
            sourceType="stream", product=ProductEnum.CONNECT, stream=ReleaseStreamEnum.DAILY, os=[_os]
        )
        assert dev_version.get_version() == expected_version
        assert dev_version.get_url_by_os()[_os.name] == expected_url
        assert str(_os.artifactDownloadURL) == expected_url

    @pytest.mark.parametrize(
        "_os,expected_version,expected_url",
        [
            pytest.param(
                ImageVersionOS(name="Debian 12"),
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/deb/amd64/rstudio-pm_2024.11.0-7_amd64.deb",
                id="debian-12",
            ),
            pytest.param(
                ImageVersionOS(name="Debian 11"),
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/deb/amd64/rstudio-pm_2024.11.0-7_amd64.deb",
                id="debian-11",
            ),
            pytest.param(
                ImageVersionOS(name="Ubuntu 24.04"),
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/deb/amd64/rstudio-pm_2024.11.0-7_amd64.deb",
                id="ubuntu-24",
            ),
            pytest.param(
                ImageVersionOS(name="Ubuntu 22.04"),
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/deb/amd64/rstudio-pm_2024.11.0-7_amd64.deb",
                id="ubuntu-22",
            ),
            pytest.param(
                ImageVersionOS(name="AlmaLinux 8"),
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/rpm/x86_64/rstudio-pm-2024.11.0-7.x86_64.rpm",
                id="alma-8",
            ),
            pytest.param(
                ImageVersionOS(name="Rocky Linux 8"),
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/rpm/x86_64/rstudio-pm-2024.11.0-7.x86_64.rpm",
                id="rocky-8",
            ),
            pytest.param(
                ImageVersionOS(name="RHEL 8"),
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/rpm/x86_64/rstudio-pm-2024.11.0-7.x86_64.rpm",
                id="rhel-8",
            ),
            pytest.param(
                ImageVersionOS(name="AlmaLinux 9"),
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/rpm/x86_64/rstudio-pm-2024.11.0-7.x86_64.rpm",
                id="alma-9",
            ),
            pytest.param(
                ImageVersionOS(name="Rocky Linux 9"),
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/rpm/x86_64/rstudio-pm-2024.11.0-7.x86_64.rpm",
                id="rocky-9",
            ),
            pytest.param(
                ImageVersionOS(name="RHEL 9"),
                "2024.11.0-7",
                "https://cdn.rstudio.com/package-manager/rpm/x86_64/rstudio-pm-2024.11.0-7.x86_64.rpm",
                id="rhel-9",
            ),
        ],
    )
    def test_package_manager_release(
        self, patch_requests_get, _os: ImageVersionOS, expected_version: str, expected_url: str
    ):
        """Test that the correct URL is returned for a release version of PPM Release"""
        dev_version = ImageDevelopmentVersionFromProductStream(
            sourceType="stream", product=ProductEnum.PACKAGE_MANAGER, stream=ReleaseStreamEnum.RELEASE, os=[_os]
        )
        assert dev_version.get_version() == expected_version
        assert dev_version.get_url_by_os()[_os.name] == expected_url
        assert str(_os.artifactDownloadURL) == expected_url

    @pytest.mark.parametrize(
        "_os,expected_version,expected_url",
        [
            pytest.param(
                ImageVersionOS(name="Debian 12"),
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2024.11.1-3776_amd64.deb",
                id="debian-12",
            ),
            pytest.param(
                ImageVersionOS(name="Debian 11"),
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2024.11.1-3776_amd64.deb",
                id="debian-11",
            ),
            pytest.param(
                ImageVersionOS(name="Ubuntu 24.04"),
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2024.11.1-3776_amd64.deb",
                id="ubuntu-24",
            ),
            pytest.param(
                ImageVersionOS(name="Ubuntu 22.04"),
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2024.11.1-3776_amd64.deb",
                id="ubuntu-22",
            ),
            pytest.param(
                ImageVersionOS(name="AlmaLinux 8"),
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.1-3776.x86_64.rpm",
                id="alma-8",
            ),
            pytest.param(
                ImageVersionOS(name="Rocky Linux 8"),
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.1-3776.x86_64.rpm",
                id="rocky-8",
            ),
            pytest.param(
                ImageVersionOS(name="RHEL 8"),
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.1-3776.x86_64.rpm",
                id="rhel-8",
            ),
            pytest.param(
                ImageVersionOS(name="AlmaLinux 9"),
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.1-3776.x86_64.rpm",
                id="alma-9",
            ),
            pytest.param(
                ImageVersionOS(name="Rocky Linux 9"),
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.1-3776.x86_64.rpm",
                id="rocky-9",
            ),
            pytest.param(
                ImageVersionOS(name="RHEL 9"),
                "2024.11.1-3776",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.1-3776.x86_64.rpm",
                id="rhel-9",
            ),
        ],
    )
    def test_package_manager_preview(
        self, patch_requests_get, _os: ImageVersionOS, expected_version: str, expected_url: str
    ):
        """Test that the correct URL is returned for a release version of PPM Preview"""
        dev_version = ImageDevelopmentVersionFromProductStream(
            sourceType="stream", product=ProductEnum.PACKAGE_MANAGER, stream=ReleaseStreamEnum.PREVIEW, os=[_os]
        )
        assert dev_version.get_version() == expected_version
        assert dev_version.get_url_by_os()[_os.name] == expected_url
        assert str(_os.artifactDownloadURL) == expected_url

    @pytest.mark.parametrize(
        "_os,expected_version,expected_url",
        [
            pytest.param(
                ImageVersionOS(name="Debian 12"),
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2024.11.2-9_amd64.deb",
                id="debian-12",
            ),
            pytest.param(
                ImageVersionOS(name="Debian 11"),
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2024.11.2-9_amd64.deb",
                id="debian-11",
            ),
            pytest.param(
                ImageVersionOS(name="Ubuntu 24.04"),
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2024.11.2-9_amd64.deb",
                id="ubuntu-24",
            ),
            pytest.param(
                ImageVersionOS(name="Ubuntu 22.04"),
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm_2024.11.2-9_amd64.deb",
                id="ubuntu-22",
            ),
            pytest.param(
                ImageVersionOS(name="AlmaLinux 8"),
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.2-9.x86_64.rpm",
                id="alma-8",
            ),
            pytest.param(
                ImageVersionOS(name="Rocky Linux 8"),
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.2-9.x86_64.rpm",
                id="rocky-8",
            ),
            pytest.param(
                ImageVersionOS(name="RHEL 8"),
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.2-9.x86_64.rpm",
                id="rhel-8",
            ),
            pytest.param(
                ImageVersionOS(name="AlmaLinux 9"),
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.2-9.x86_64.rpm",
                id="alma-9",
            ),
            pytest.param(
                ImageVersionOS(name="Rocky Linux 9"),
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.2-9.x86_64.rpm",
                id="rocky-9",
            ),
            pytest.param(
                ImageVersionOS(name="RHEL 9"),
                "2024.11.2-9",
                "https://cdn.posit.co/package-manager/rpm/x86_64/rstudio-pm-2024.11.2-9.x86_64.rpm",
                id="rhel-9",
            ),
        ],
    )
    def test_package_manager_daily(
        self, patch_requests_get, _os: ImageVersionOS, expected_version: str, expected_url: str
    ):
        """Test that the correct URL is returned for a release version of PPM Daily"""
        dev_version = ImageDevelopmentVersionFromProductStream(
            sourceType="stream", product=ProductEnum.PACKAGE_MANAGER, stream=ReleaseStreamEnum.DAILY, os=[_os]
        )
        assert dev_version.get_version() == expected_version
        assert dev_version.get_url_by_os()[_os.name] == expected_url
        assert str(_os.artifactDownloadURL) == expected_url

    @pytest.mark.parametrize(
        "_os,expected_version,expected_url,expected_session_url",
        [
            pytest.param(
                ImageVersionOS(name="Debian 12"),
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/jammy/amd64/rstudio-workbench-2024.12.1-563.pro5-amd64.deb",
                "https://download1.rstudio.org/session/jammy/amd64/rsp-session-jammy-2024.12.1-563.pro5-amd64.tar.gz",
                id="debian-12",
            ),
            pytest.param(
                ImageVersionOS(name="Debian 11"),
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/jammy/amd64/rstudio-workbench-2024.12.1-563.pro5-amd64.deb",
                "https://download1.rstudio.org/session/jammy/amd64/rsp-session-jammy-2024.12.1-563.pro5-amd64.tar.gz",
                id="debian-11",
            ),
            pytest.param(
                ImageVersionOS(name="Ubuntu 24.04"),
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/jammy/amd64/rstudio-workbench-2024.12.1-563.pro5-amd64.deb",
                "https://download1.rstudio.org/session/jammy/amd64/rsp-session-jammy-2024.12.1-563.pro5-amd64.tar.gz",
                id="ubuntu-24",
            ),
            pytest.param(
                ImageVersionOS(name="Ubuntu 22.04"),
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/jammy/amd64/rstudio-workbench-2024.12.1-563.pro5-amd64.deb",
                "https://download1.rstudio.org/session/jammy/amd64/rsp-session-jammy-2024.12.1-563.pro5-amd64.tar.gz",
                id="ubuntu-22",
            ),
            pytest.param(
                ImageVersionOS(name="AlmaLinux 8"),
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/rhel8/x86_64/"
                "rstudio-workbench-rhel-2024.12.1-563.pro5-x86_64.rpm",
                "https://download1.rstudio.org/session/rhel8/x86_64/rsp-session-rhel8-2024.12.1-563.pro5-x86_64.tar.gz",
                id="alma-8",
            ),
            pytest.param(
                ImageVersionOS(name="Rocky Linux 8"),
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/rhel8/x86_64/"
                "rstudio-workbench-rhel-2024.12.1-563.pro5-x86_64.rpm",
                "https://download1.rstudio.org/session/rhel8/x86_64/rsp-session-rhel8-2024.12.1-563.pro5-x86_64.tar.gz",
                id="rocky-8",
            ),
            pytest.param(
                ImageVersionOS(name="RHEL 8"),
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/rhel8/x86_64/"
                "rstudio-workbench-rhel-2024.12.1-563.pro5-x86_64.rpm",
                "https://download1.rstudio.org/session/rhel8/x86_64/rsp-session-rhel8-2024.12.1-563.pro5-x86_64.tar.gz",
                id="rhel-8",
            ),
            pytest.param(
                ImageVersionOS(name="AlmaLinux 9"),
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/rhel9/x86_64/"
                "rstudio-workbench-rhel-2024.12.1-563.pro5-x86_64.rpm",
                "https://download1.rstudio.org/session/rhel9/x86_64/rsp-session-rhel9-2024.12.1-563.pro5-x86_64.tar.gz",
                id="alma-9",
            ),
            pytest.param(
                ImageVersionOS(name="Rocky Linux 9"),
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/rhel9/x86_64/"
                "rstudio-workbench-rhel-2024.12.1-563.pro5-x86_64.rpm",
                "https://download1.rstudio.org/session/rhel9/x86_64/rsp-session-rhel9-2024.12.1-563.pro5-x86_64.tar.gz",
                id="rocky-9",
            ),
            pytest.param(
                ImageVersionOS(name="RHEL 9"),
                "2024.12.1+563.pro5",
                "https://download2.rstudio.org/server/rhel9/x86_64/rstudio-workbench-rhel-2024.12.1-563.pro5-x86_64.rpm",
                "https://download1.rstudio.org/session/rhel9/x86_64/rsp-session-rhel9-2024.12.1-563.pro5-x86_64.tar.gz",
                id="rhel-9",
            ),
        ],
    )
    def test_workbench_release(
        self,
        patch_requests_get,
        _os: ImageVersionOS,
        expected_version: str,
        expected_url: str,
        expected_session_url: str,
    ):
        """Test that the correct URL is returned for a release version of Workbench Release"""
        dev_version = ImageDevelopmentVersionFromProductStream(
            sourceType="stream", product=ProductEnum.WORKBENCH, stream=ReleaseStreamEnum.RELEASE, os=[_os]
        )
        assert dev_version.get_version() == expected_version
        assert dev_version.get_url_by_os()[_os.name] == expected_url
        assert str(_os.artifactDownloadURL) == expected_url

        dev_version = ImageDevelopmentVersionFromProductStream(
            sourceType="stream", product=ProductEnum.WORKBENCH_SESSION, stream=ReleaseStreamEnum.RELEASE, os=[_os]
        )
        assert dev_version.get_version() == expected_version
        assert dev_version.get_url_by_os()[_os.name] == expected_session_url
        assert str(_os.artifactDownloadURL) == expected_session_url

    @pytest.mark.parametrize(
        "_os,expected_version,expected_url,expected_session_url",
        [
            pytest.param(
                ImageVersionOS(name="Debian 12"),
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/jammy/amd64/"
                "rstudio-workbench-2025.04.0-daily-404.pro4-amd64.deb",
                "https://s3.amazonaws.com/rstudio-ide-build/session/jammy/amd64/"
                "rsp-session-jammy-2025.04.0-daily-404.pro4-amd64.tar.gz",
                id="debian-12",
            ),
            pytest.param(
                ImageVersionOS(name="Debian 11"),
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/jammy/amd64/"
                "rstudio-workbench-2025.04.0-daily-404.pro4-amd64.deb",
                "https://s3.amazonaws.com/rstudio-ide-build/session/jammy/amd64/"
                "rsp-session-jammy-2025.04.0-daily-404.pro4-amd64.tar.gz",
                id="debian-11",
            ),
            pytest.param(
                ImageVersionOS(name="Ubuntu 24.04"),
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/jammy/amd64/"
                "rstudio-workbench-2025.04.0-daily-404.pro4-amd64.deb",
                "https://s3.amazonaws.com/rstudio-ide-build/session/jammy/amd64/"
                "rsp-session-jammy-2025.04.0-daily-404.pro4-amd64.tar.gz",
                id="ubuntu-24",
            ),
            pytest.param(
                ImageVersionOS(name="Ubuntu 22.04"),
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/jammy/amd64/"
                "rstudio-workbench-2025.04.0-daily-404.pro4-amd64.deb",
                "https://s3.amazonaws.com/rstudio-ide-build/session/jammy/amd64/"
                "rsp-session-jammy-2025.04.0-daily-404.pro4-amd64.tar.gz",
                id="ubuntu-22",
            ),
            pytest.param(
                ImageVersionOS(name="AlmaLinux 8"),
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/rhel8/x86_64/"
                "rstudio-workbench-rhel-2025.04.0-daily-404.pro4-x86_64.rpm",
                "https://s3.amazonaws.com/rstudio-ide-build/session/rhel8/x86_64/"
                "rsp-session-rhel8-2025.04.0-daily-404.pro4-x86_64.tar.gz",
                id="alma-8",
            ),
            pytest.param(
                ImageVersionOS(name="Rocky Linux 8"),
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/rhel8/x86_64/"
                "rstudio-workbench-rhel-2025.04.0-daily-404.pro4-x86_64.rpm",
                "https://s3.amazonaws.com/rstudio-ide-build/session/rhel8/x86_64/"
                "rsp-session-rhel8-2025.04.0-daily-404.pro4-x86_64.tar.gz",
                id="rocky-8",
            ),
            pytest.param(
                ImageVersionOS(name="RHEL 8"),
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/rhel8/x86_64/"
                "rstudio-workbench-rhel-2025.04.0-daily-404.pro4-x86_64.rpm",
                "https://s3.amazonaws.com/rstudio-ide-build/session/rhel8/x86_64/"
                "rsp-session-rhel8-2025.04.0-daily-404.pro4-x86_64.tar.gz",
                id="rhel-8",
            ),
            pytest.param(
                ImageVersionOS(name="AlmaLinux 9"),
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/rhel9/x86_64/"
                "rstudio-workbench-rhel-2025.04.0-daily-404.pro4-x86_64.rpm",
                "https://s3.amazonaws.com/rstudio-ide-build/session/rhel9/x86_64/"
                "rsp-session-rhel9-2025.04.0-daily-404.pro4-x86_64.tar.gz",
                id="alma-9",
            ),
            pytest.param(
                ImageVersionOS(name="Rocky Linux 9"),
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/rhel9/x86_64/"
                "rstudio-workbench-rhel-2025.04.0-daily-404.pro4-x86_64.rpm",
                "https://s3.amazonaws.com/rstudio-ide-build/session/rhel9/x86_64/"
                "rsp-session-rhel9-2025.04.0-daily-404.pro4-x86_64.tar.gz",
                id="rocky-9",
            ),
            pytest.param(
                ImageVersionOS(name="RHEL 9"),
                "2025.04.0-daily+404.pro4",
                "https://s3.amazonaws.com/rstudio-ide-build/server/rhel9/x86_64/"
                "rstudio-workbench-rhel-2025.04.0-daily-404.pro4-x86_64.rpm",
                "https://s3.amazonaws.com/rstudio-ide-build/session/rhel9/x86_64/"
                "rsp-session-rhel9-2025.04.0-daily-404.pro4-x86_64.tar.gz",
                id="rhel-9",
            ),
        ],
    )
    def test_workbench_daily(
        self,
        patch_requests_get,
        _os: ImageVersionOS,
        expected_version: str,
        expected_url: str,
        expected_session_url: str,
    ):
        """Test that the correct URL is returned for a release version of Workbench Daily"""
        dev_version = ImageDevelopmentVersionFromProductStream(
            sourceType="stream", product=ProductEnum.WORKBENCH, stream=ReleaseStreamEnum.DAILY, os=[_os]
        )
        assert dev_version.get_version() == expected_version
        assert dev_version.get_url_by_os()[_os.name] == expected_url
        assert str(_os.artifactDownloadURL) == expected_url

        dev_version = ImageDevelopmentVersionFromProductStream(
            sourceType="stream", product=ProductEnum.WORKBENCH_SESSION, stream=ReleaseStreamEnum.DAILY, os=[_os]
        )
        assert dev_version.get_version() == expected_version
        assert dev_version.get_url_by_os()[_os.name] == expected_session_url
        assert str(_os.artifactDownloadURL) == expected_session_url
