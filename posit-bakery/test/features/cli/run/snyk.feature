@functional
Feature: snyk

    @slow
    Scenario: Running snyk container test on a project
        Given I call bakery build
        * in the barebones context
        * with the arguments:
            | --load |
        When I execute the command
        Then The command succeeds

        Given I call bakery run snyk
        * in the barebones context
        * with the arguments:
            | test |
        When I execute the command
        Then The command succeeds
        * the stderr output includes:
            | snyk container test command(s) completed |

    @slow
    Scenario: Running snyk container sbom on a project
        Given I call bakery build
        * in the barebones context
        * with the arguments:
            | --load |
        When I execute the command
        Then The command succeeds

        Given I call bakery run snyk
        * in the barebones context
        * with the arguments:
            | sbom |
        When I execute the command
        Then The command succeeds
        * the stderr output includes:
            | snyk container sbom command(s) completed |
