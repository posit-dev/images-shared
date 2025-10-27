from pytest_bdd import scenarios

scenarios(
    "cli/get/images.feature",
    "cli/get/registries.feature",
    "cli/get/versions.feature",
)
