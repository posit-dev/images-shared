import pulumi

from github_apps.app import AppConfig, manage_app


def deploy():
    config = pulumi.Config("github-apps")
    apps: dict[str, dict] = config.require_object("apps")

    for app_name, app_def in apps.items():
        app_config = AppConfig(
            name=app_name,
            installation_id=app_def.get("installationId", ""),
            secret_prefix=app_def.get("secretPrefix", ""),
            secrets=app_def.get("secrets", []),
            repositories=app_def.get("repositories", []),
            dispatch_only=app_def.get("dispatchOnly", []),
        )
        manage_app(app_config)
