@functional
Feature: bakery

    Scenario: bakery help
        Given I run bakery
        * with the "help" flag
        When I execute the command
        Then The command succeeds
        * help is shown

    Scenario: bakery with unknown flag
        Given I run bakery
        * with the "fakename" flag
        When I execute the command
        Then The command fails
        * help is shown

    Scenario: bakery with unknown command
        Given I run bakery
        * with the "nope" arguments
        When I execute the command
        Then The command fails
        * help is shown

    Scenario: bakery with unknown option
        Given I run bakery
        * with the "planet" option set to "mars"
        When I execute the command
        Then The command fails
        * help is shown
