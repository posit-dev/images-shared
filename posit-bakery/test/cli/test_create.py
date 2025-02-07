from pytest_bdd import scenarios

scenarios(
    "cli/create/project.feature",
    "cli/create/image.feature",
    "cli/create/version.feature",
)
