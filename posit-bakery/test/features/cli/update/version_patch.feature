@functional
Feature: update version

    Scenario: Updating a version by edition auto-detection
        Given I call bakery update version
        * in a temp calver context
        * with the arguments:
            | test-image |
            | 2026.02.1 |
        When I execute the command
        Then The command succeeds
        * the image "test-image" exists
        * the version "2026.02.1" exists in the "2026.02" subpath
        * the default rendered templates exist in the "2026.02" subpath
        * the stderr output includes:
            | Successfully updated |
            | '2026.02.0' to '2026.02.1' |
