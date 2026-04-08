import pulumi

from github_apps.app import AppConfig, manage_app
from github_apps.apps import APPS


def deploy():
    github_config = pulumi.Config("github")
    owner = github_config.require("owner")

    # Installation IDs are the only per-org config. They live in stack
    # config because they're assigned by GitHub when the app is installed.
    config = pulumi.Config("github-apps")
    installation_ids: dict[str, str] = config.get_object("installationIds") or {}

    for app_name, app_def in APPS.items():
        org_config = app_def.get("orgs", {}).get(owner)
        if org_config is None:
            continue

        manage_app(
            AppConfig(
                name=app_name,
                installation_id=installation_ids.get(app_name, ""),
                secret_prefix=app_def.get("secret_prefix", ""),
                secrets=app_def.get("secrets", []),
                repositories=org_config.get("repositories", []),
                dispatch_only=org_config.get("dispatch_only", []),
            )
        )
