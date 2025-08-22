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
