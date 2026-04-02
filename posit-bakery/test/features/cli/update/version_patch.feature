@functional
Feature: update version

    Scenario: Updating the latest version by default
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

    Scenario: Updating a version with explicit target
        Given I call bakery update version
        * in a temp calver context
        * with the arguments:
            | test-image |
            | 2026.02.1 |
            | --target-version |
            | 2026.02.0 |
        When I execute the command
        Then The command succeeds
        * the image "test-image" exists
        * the version "2026.02.1" exists in the "2026.02" subpath
        * the default rendered templates exist in the "2026.02" subpath
        * the stderr output includes:
            | Successfully updated |
            | '2026.02.0' to '2026.02.1' |
