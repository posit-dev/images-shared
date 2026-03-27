@functional
Feature: get version

    Scenario: Get version by edition match
        Given I call bakery get version
        * in a temp calver context
        * with the arguments:
            | test-image |
            | 2026.02.0 |
        When I execute the command
        Then The command succeeds
        * the stdout output includes:
            | 2026.02.0 |

    Scenario: Get latest version
        Given I call bakery get version
        * in a temp calver context
        * with the arguments:
            | test-image |
            | --latest |
        When I execute the command
        Then The command succeeds
        * the stdout output includes:
            | 2026.02.0 |

    Scenario: Get version not found
        Given I call bakery get version
        * in a temp calver context
        * with the arguments:
            | test-image |
            | 9999.01.0 |
        When I execute the command
        Then The command fails
