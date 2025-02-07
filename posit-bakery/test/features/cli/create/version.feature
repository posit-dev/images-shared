@functional
Feature: create version

    Scenario: bakery create version
        Given I call bakery "create" "version"
        * in a temp basic context
        * with the arguments:
            | test-image |
            | 1.1.0 |
        When I execute the command
        Then The command succeeds
        * the image "test-image" exists
        * the version "1.1.0" exists
        * the default rendered templates exist
        * the stderr output includes:
            | Successfully created version 'test-image/1.1.0' |
