@functional
Feature: update version patch

    Scenario: Updating a version patch
        Given I call bakery update version patch
        * in a temp basic context
        * with the arguments:
            | test-image |
            | 1.0.0 |
            | 1.0.1 |
        When I execute the command
        Then The command succeeds
        * the image "test-image" exists
        * the version "1.0.1" exists
        * the version "1.0.1" does not exist
        * the default rendered templates exist
        * the stderr output includes:
            | Successfully patched version |
            | 'test-image/1.0.0' to 'test-image/1.0.1' |
