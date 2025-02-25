@functional
Feature: dgoss

    @slow
    Scenario: bakery run dgoss
        Given I call bakery build
        * in a temp basic context
        * with the arguments:
            | --load |
        When I execute the command
        Then The command succeeds

        Given I call bakery run dgoss
        * in a temp basic context
        When I execute the command
        Then The command succeeds
        * the stderr output includes:
            | Tests completed |
        * the context includes files:
            | results/dgoss/test-image/test-image-1-0-0-ubuntu2204-min.json |
            | results/dgoss/test-image/test-image-1-0-0-ubuntu2204-std.json |
