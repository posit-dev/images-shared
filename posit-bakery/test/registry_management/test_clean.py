"""Tests for registry_management.clean module."""

from datetime import timedelta

import pytest

from posit_bakery.config import BakeryConfig
from posit_bakery.config.config import BakerySettings
from posit_bakery.registry_management.clean import clean_caches, clean_temporary
from posit_bakery.targets.selection import select_targets

pytestmark = pytest.mark.unit


class TestCleanCaches:
    """Tests for clean_caches function."""

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
        """Test cleaning caches in the registry."""
        context = get_tmpcontext("basic")
        cache_registry = "ghcr.io/posit-test"
        settings = BakerySettings(cache_registry=cache_registry)
        config = BakeryConfig.from_context(context, settings)

        mock_ghcr_client = mocker.patch("posit_bakery.registry_management.ghcr.clean.GHCRClient")
        mock_ghcr_client_instance = mock_ghcr_client.return_value
        mock_ghcr_client_instance.get_package_versions.return_value = cache_ghcr_package_versions_data

        # Clean caches
        clean_caches(
            targets=select_targets(config, config.settings),
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
        """Test cleaning caches in dry-run mode."""
        context = get_tmpcontext("basic")
        cache_registry = "ghcr.io/posit-test"
        settings = BakerySettings(cache_registry=cache_registry)
        config = BakeryConfig.from_context(context, settings)

        mock_ghcr_client = mocker.patch("posit_bakery.registry_management.ghcr.clean.GHCRClient")
        mock_ghcr_client_instance = mock_ghcr_client.return_value
        mock_ghcr_client_instance.get_package_versions.return_value = cache_ghcr_package_versions_data

        # Clean caches
        clean_caches(
            targets=select_targets(config, config.settings),
            remove_untagged=True,
            remove_older_than=timedelta(days=14),
            dry_run=True,
        )

        mock_ghcr_client.assert_called_once()
        mock_ghcr_client_instance.get_package_versions.assert_called_once()
        mock_ghcr_client_instance.delete_package_version.assert_not_called()


class TestCleanTemporary:
    """Tests for clean_temporary function."""

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
        """Test cleaning temporary images in the registry."""
        context = get_tmpcontext("basic")
        temp_registry = "ghcr.io/posit-test"
        settings = BakerySettings(temp_registry=temp_registry)
        config = BakeryConfig.from_context(context, settings)

        mock_ghcr_client = mocker.patch("posit_bakery.registry_management.ghcr.clean.GHCRClient")
        mock_ghcr_client_instance = mock_ghcr_client.return_value
        mock_ghcr_client_instance.get_package_versions.return_value = temp_ghcr_package_versions_data

        # Clean temp images
        clean_temporary(
            targets=select_targets(config, config.settings),
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
        """Test cleaning temp images in dry-run mode."""
        context = get_tmpcontext("basic")
        temp_registry = "ghcr.io/posit-test"
        settings = BakerySettings(temp_registry=temp_registry)
        config = BakeryConfig.from_context(context, settings)

        mock_ghcr_client = mocker.patch("posit_bakery.registry_management.ghcr.clean.GHCRClient")
        mock_ghcr_client_instance = mock_ghcr_client.return_value
        mock_ghcr_client_instance.get_package_versions.return_value = temp_ghcr_package_versions_data

        # Clean temp images
        clean_temporary(
            targets=select_targets(config, config.settings),
            remove_untagged=True,
            remove_older_than=timedelta(days=14),
            dry_run=True,
        )

        mock_ghcr_client.assert_called_once()
        mock_ghcr_client_instance.get_package_versions.assert_called_once()
        mock_ghcr_client_instance.delete_package_version.assert_not_called()
