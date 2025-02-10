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
    Scenario: Building images from a project
        Given I call bakery build
        * in a temp basic context
        * with the arguments:
            | --load |
        When I execute the command
        Then The command succeeds
        * the stderr output includes:
            | Build completed |
