from dataclasses import dataclass, field

import pulumi
from pulumi import ResourceOptions
from pulumi_github import (
    AppInstallationRepositories,
    ActionsOrganizationSecret,
    ActionsOrganizationSecretRepositories,
    get_repository,
)


@dataclass
class AppConfig:
    """Configuration for a GitHub App and its installations."""

    name: str
    installation_id: str
    secret_prefix: str = ""
    secrets: list[str] = field(default_factory=list)
    repositories: list[str] = field(default_factory=list)
    dispatch_only: list[str] = field(default_factory=list)


def manage_app(app: AppConfig):
    """Manage a GitHub App's repository installations and secret sharing.

    For each app:
    1. Install the app on the specified repositories.
    2. For each secret the app declares, ensure an org-level secret exists
       with visibility=selected and share it with the app's repositories.
    """
    if not app.installation_id:
        pulumi.warn(
            f"Skipping {app.name}: no installationId configured. "
            f"Create the GitHub App and set the installation ID in the stack config."
        )
        return

    # Install the app on all repos (both secret-sharing and dispatch-only).
    all_repos = app.repositories + app.dispatch_only
    if not all_repos:
        pulumi.warn(f"Skipping {app.name}: no repositories or dispatchOnly configured.")
        return

    AppInstallationRepositories(
        f"{app.name}-repos",
        installation_id=app.installation_id,
        selected_repositories=all_repos,
    )

    if not app.secrets:
        return

    # Resolve repository IDs for secret sharing (excludes dispatch-only repos).
    repo_ids = []
    for repo_name in app.repositories:
        repo = get_repository(name=repo_name)
        repo_ids.append(repo.repo_id)

    prefix = app.secret_prefix or _secret_prefix(app.name)
    for secret_name in app.secrets:
        org_secret_name = f"{prefix}_{secret_name}"

        # Pulumi manages the resource and repo sharing. The actual value
        # is set out-of-band via gh secret set to avoid storing secrets
        # in Pulumi state or git history.
        secret = ActionsOrganizationSecret(
            f"{app.name}-secret-{secret_name}",
            secret_name=org_secret_name,
            visibility="selected",
            plaintext_value="CHANGE_ME",
            opts=ResourceOptions(
                ignore_changes=["plaintext_value", "encrypted_value"],
            ),
        )

        ActionsOrganizationSecretRepositories(
            f"{app.name}-secret-{secret_name}-repos",
            secret_name=org_secret_name,
            selected_repository_ids=repo_ids,
            opts=ResourceOptions(depends_on=[secret]),
        )


def _secret_prefix(app_name: str) -> str:
    """Convert an app name like 'connect-bot' to 'CONNECT_BOT'."""
    return app_name.upper().replace("-", "_")
