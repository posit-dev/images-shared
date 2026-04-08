"""GitHub App definitions for the Posit container image ecosystem.

Each app is defined once. Per-org repository lists specify where the app
is installed and whether secrets are shared. Installation IDs come from
stack config since they differ per org.

To add a repo:  add it to the appropriate org's repositories or dispatch_only list.
To add an app:  add a new top-level entry following the existing pattern.
To add an org:  add a new key under orgs for the relevant apps.
"""

APPS: dict[str, dict] = {
    # ------------------------------------------------------------------ #
    # Product bots — one per product, owns the dispatch chain from
    # product release through image build to helm chart update.
    # ------------------------------------------------------------------ #
    "connect-bot": {
        "secrets": ["APP_ID", "APP_PRIVATE_KEY"],
        "orgs": {
            "posit-dev": {
                "repositories": ["connect", "images-connect"],
            },
            "rstudio": {
                # No secrets — images-connect uses posit-dev org secrets
                # with actions/create-github-app-token (owner: rstudio)
                # to generate a token scoped to rstudio/helm.
                "dispatch_only": ["helm"],
            },
        },
    },
    "workbench-bot": {
        "secrets": ["APP_ID", "APP_PRIVATE_KEY"],
        "orgs": {
            "posit-dev": {
                "repositories": ["images-workbench"],
            },
            "rstudio": {
                "repositories": ["rstudio-pro"],
                "dispatch_only": ["helm"],
            },
        },
    },
    "ppm-bot": {
        "secrets": ["APP_ID", "APP_PRIVATE_KEY"],
        "orgs": {
            "posit-dev": {
                "repositories": ["images-package-manager"],
            },
            "rstudio": {
                "repositories": ["package-manager"],
                "dispatch_only": ["helm"],
            },
        },
    },
    # ------------------------------------------------------------------ #
    # Platform bot — platform team operations (scheduled rebuilds, cache
    # cleanup). Centralized dispatch is a future option.
    # ------------------------------------------------------------------ #
    "platform-bot": {
        "secrets": ["APP_ID", "APP_PRIVATE_KEY"],
        "orgs": {
            "posit-dev": {
                "repositories": ["images-shared"],
            },
            "rstudio": {
                "repositories": ["helm"],
            },
        },
    },
    # ------------------------------------------------------------------ #
    # Posit Docs — runs the doc-reviewer skill on PRs. Secrets use the
    # POSIT_DOCS_ prefix to match existing org secret names.
    # ------------------------------------------------------------------ #
    "posit-docs": {
        "secret_prefix": "POSIT_DOCS",
        "secrets": ["APP_ID", "PEM"],
        "orgs": {
            "posit-dev": {
                "repositories": ["connect", "troubleshooting", "data-sources"],
                "dispatch_only": ["doc-reviewer"],
            },
            "rstudio": {
                "repositories": ["docs.rstudio.com", "package-manager"],
            },
        },
    },
}
