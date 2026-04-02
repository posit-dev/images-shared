@functional
Feature: get version

    Scenario: Get latest version by default
        Given I call bakery get version
        * in a temp calver context
        * with the arguments:
            | test-image |
        When I execute the command
        Then The command succeeds
        * the stdout output includes:
            | 2026.02.0 |

    Scenario: Get latest version with explicit flag
        Given I call bakery get version
        * in a temp calver context
        * with the arguments:
            | test-image |
            | --latest |
        When I execute the command
        Then The command succeeds
        * the stdout output includes:
            | 2026.02.0 |

    Scenario: Get version by subpath
        Given I call bakery get version
        * in a temp calver context
        * with the arguments:
            | test-image |
            | --subpath |
            | 2026.02 |
        When I execute the command
        Then The command succeeds
        * the stdout output includes:
            | 2026.02.0 |

    Scenario: Get version by subpath not found
        Given I call bakery get version
        * in a temp calver context
        * with the arguments:
            | test-image |
            | --subpath |
            | 9999.01 |
        When I execute the command
        Then The command fails
