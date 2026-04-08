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
    secrets: list[str] = field(default_factory=list)
    repositories: list[str] = field(default_factory=list)
    dispatch_only: list[str] = field(default_factory=list)


def manage_app(owner: str, app: AppConfig):
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

    # For each secret this app declares, ensure the org-level secret is
    # shared with the app's repositories. The secret value itself is
    # managed outside of Pulumi (stored in the org, set via gh CLI or UI).
    # We only manage *which repos* can access it.
    for secret_name in app.secrets:
        # Namespace the secret per app so each bot has its own credentials.
        org_secret_name = f"{_secret_prefix(app.name)}_{secret_name}"

        # Create the org secret as a placeholder. The actual value must be
        # set out-of-band (gh secret set, GitHub UI, etc.) because Pulumi
        # would store it in state. We use a sentinel to create the resource.
        ActionsOrganizationSecret(
            f"{app.name}-secret-{secret_name}",
            secret_name=org_secret_name,
            visibility="selected",
            plaintext_value="PLACEHOLDER_SET_VIA_GH_CLI",
            opts=ResourceOptions(
                ignore_changes=["plaintext_value", "encrypted_value"],
            ),
        )

        ActionsOrganizationSecretRepositories(
            f"{app.name}-secret-{secret_name}-repos",
            secret_name=org_secret_name,
            selected_repository_ids=repo_ids,
        )


def _secret_prefix(app_name: str) -> str:
    """Convert an app name like 'connect-bot' to 'CONNECT_BOT'."""
    return app_name.upper().replace("-", "_")
