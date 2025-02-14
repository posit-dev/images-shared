@functional
Feature: snyk

    @slow
    Scenario: Running snyk test on a project
        Given I call bakery build
        * in a temp basic context
        * with the arguments:
            | --load |
        When I execute the command
        Then The command succeeds

        Given I call bakery run snyk
        * in a temp basic context
        * with the arguments:
            | test |
        When I execute the command
        Then The command succeeds
        * the stderr output includes:
            | Tests completed |
