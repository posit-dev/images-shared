@functional
Feature: build

    Scenario: Generating a buildkit bake plan
        Given I call bakery build
        * in a temp basic context
        * with the arguments:
            | --plan |
        When I execute the command
        Then The command succeeds
        * the bake plan is valid

    Scenario: Generating a buildkit bake plan with git commit
        Given I call bakery build
        * in the basic context
        * with the arguments:
            | --plan |
        When I execute the command
        Then The command succeeds
        * the bake plan is valid
        * the targets include the commit hash

    @slow
    @xdist-build
    Scenario: Building images from a project using bake
        Given I call bakery build
        * in a temp basic context
        When I execute the command
        Then The command succeeds
        * the stderr output includes:
            | Build completed |
        * the basic test suite is built
        * the basic images are removed

    @slow
    @xdist-build
    Scenario: Building images from a project using sequential build
        Given I call bakery build
        * in a temp basic context
        * with the arguments:
            | --strategy | build |
        When I execute the command
        Then The command succeeds
        * the stderr output includes:
            | Build completed |
        * the basic test suite is built
        * the basic images are removed

    @slow
    @xdist-build
    Scenario: Building images from a project using sequential build with --fail-fast
        Given I call bakery build
        * in a temp fail-fast context
        * with the arguments:
            | --strategy | build | --fail-fast |
        When I execute the command
        Then The command exits with code 1
        * the stderr output includes:
            | Build failed |
        * the fail-fast test suite is not built
        * the fail-fast images are removed

    @slow
    @xdist-build
    Scenario: Building images that utilize Bakery's macros
        Given I call bakery build
        * in a temp with-macros context
        When I execute the command
        Then The command succeeds
        * the stderr output includes:
            | Build completed |
        * the with-macros test suite is built
        * the with-macros images are removed

    @slow
    @xdist-build
    Scenario: Building images that are multiplatform
        Given I call bakery build
        * in a temp multiplatform context
        When I execute the command
        Then The command succeeds
        * the stderr output includes:
            | Build completed |
        * the multiplatform test suite is built
        * the multiplatform test suite built for platforms:
            | linux/amd64 |
            | linux/arm64 |
        * the multiplatform images are removed

    @slow
    @xdist-build
    Scenario: Building images that are multiplatform (sequential build)
        Given I call bakery build --strategy build
        * in a temp multiplatform context
        When I execute the command
        Then The command succeeds
        * the stderr output includes:
            | Build completed |
        * the multiplatform test suite is built
        * the multiplatform test suite built for platforms:
            | linux/amd64 |
            | linux/arm64 |
        * the multiplatform images are removed

    @slow
    @xdist-build
    Scenario: Building images that are multiplatform with the platform flag overrides set platforms
        Given I call bakery build --platform linux/arm64
        * in a temp multiplatform context
        When I execute the command
        Then The command succeeds
        * the stderr output includes:
            | Build completed |
        * the multiplatform test suite is built
        * the multiplatform test suite built for platforms:
            | linux/arm64 |
        * the multiplatform test suite did not build for platforms:
            | linux/amd64 |
        * the multiplatform images are removed

    @slow
    @xdist-build
    Scenario: Building images that are multiplatform with the platform flag overrides set platforms (sequential build)
        Given I call bakery build --platform linux/arm64 --strategy build
        * in a temp multiplatform context
        When I execute the command
        Then The command succeeds
        * the stderr output includes:
            | Build completed |
        * the multiplatform test suite is built
        * the multiplatform test suite built for platforms:
            | linux/arm64 |
        * the multiplatform test suite did not build for platforms:
            | linux/amd64 |
        * the multiplatform images are removed
