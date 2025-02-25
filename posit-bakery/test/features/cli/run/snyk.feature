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
            | snyk container test |
            | command |
            | completed |

    @slow
    Scenario: Running snyk container sbom on a project
        Given I call bakery build
        * in a temp barebones context
        * with the arguments:
            | --load |
        When I execute the command
        Then The command succeeds

        Given I call bakery run snyk
        * in a temp barebones context
        * with the arguments:
            | sbom |
        When I execute the command
        Then The command succeeds
        * the stderr output includes:
            | snyk container sbom |
            | command |
            | completed |
        * the context includes files:
            | snyk_sbom/scratch-1-0-0-scratch-min.json |
            | snyk_sbom/scratch-1-0-0-scratch-std.json |
