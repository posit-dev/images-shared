import pulumi

from github_apps.app import AppConfig, manage_app


def deploy():
    config = pulumi.Config("github-apps")
    github_config = pulumi.Config("github")
    owner = github_config.require("owner")

    apps: dict[str, dict] = config.require_object("apps")

    for app_name, app_def in apps.items():
        app_config = AppConfig(
            name=app_name,
            installation_id=app_def["installationId"],
            secrets=app_def.get("secrets", []),
            repositories=app_def.get("repositories", []),
            dispatch_only=app_def.get("dispatchOnly", []),
        )
        manage_app(owner, app_config)
