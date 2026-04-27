import logging

import pytest
from github import GithubException

from posit_bakery.registry_management.ghcr.api import GHCRClient
from posit_bakery.registry_management.ghcr.models import (
    GHCRPackageVersion,
    GHCRPackageVersionContainerMetadata,
    GHCRPackageVersionMetadata,
    GHCRPackageVersions,
)


def _make_version(version_id: int) -> GHCRPackageVersion:
    return GHCRPackageVersion(
        id=version_id,
        name=f"sha256:{version_id:064x}",
        url=f"https://api.github.com/orgs/posit-test/packages/container/pkg/versions/{version_id}",
        package_html_url="https://github.com/orgs/posit-test/packages/container/package/pkg",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-02T00:00:00Z",
        html_url=f"https://github.com/orgs/posit-test/packages/container/pkg/{version_id}",
        metadata=GHCRPackageVersionMetadata(
            package_type="container",
            container=GHCRPackageVersionContainerMetadata(tags=[]),
        ),
    )


@pytest.fixture
def client(mocker):
    mocker.patch("posit_bakery.registry_management.ghcr.api.Auth")
    mocker.patch("posit_bakery.registry_management.ghcr.api.Github")
    return GHCRClient("posit-test", token="fake-token")


class TestDeletePackageVersions:
    def test_returns_no_errors_when_all_succeed(self, client, mocker):
        mocker.patch.object(client, "delete_package_version")
        versions = GHCRPackageVersions(versions=[_make_version(1), _make_version(2)])

        errors = client.delete_package_versions(versions)

        assert errors == []

    def test_collects_errors_for_generic_failures(self, client, mocker):
        mocker.patch.object(
            client,
            "delete_package_version",
            side_effect=GithubException(500, data={}, message="Internal server error"),
        )
        versions = GHCRPackageVersions(versions=[_make_version(1)])

        errors = client.delete_package_versions(versions)

        assert len(errors) == 1
        assert errors[0] == (1, "Internal server error")

    def test_suppresses_5000_downloads_error_as_warning(self, client, mocker, caplog):
        message = (
            "Publicly visible package versions with more than 5000 downloads cannot be deleted. "
            "Contact GitHub support for further assistance."
        )
        mocker.patch.object(
            client,
            "delete_package_version",
            side_effect=GithubException(422, data={}, message=message),
        )
        versions = GHCRPackageVersions(versions=[_make_version(1)])

        with caplog.at_level(logging.WARNING, logger="posit_bakery.registry_management.ghcr.api"):
            errors = client.delete_package_versions(versions)

        assert errors == []
        assert any(
            "5000 downloads" in record.message and record.levelno == logging.WARNING for record in caplog.records
        )

    def test_mixed_results_only_reports_non_flaky_errors(self, client, mocker):
        flaky = GithubException(
            422,
            data={},
            message="Publicly visible package versions with more than 5000 downloads cannot be deleted.",
        )
        real = GithubException(500, data={}, message="Internal server error")
        mocker.patch.object(client, "delete_package_version", side_effect=[flaky, real, None])
        versions = GHCRPackageVersions(
            versions=[_make_version(1), _make_version(2), _make_version(3)],
        )

        errors = client.delete_package_versions(versions)

        assert len(errors) == 1
        assert errors[0][0] == 2
