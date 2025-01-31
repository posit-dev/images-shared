@functional
Feature: bakery

    Scenario: bakery help
        Given I call bakery
        * with the arguments:
            | --help |
        When I execute the command
        Then The command succeeds
        * usage is shown

    Scenario: bakery with unknown flag
        Given I call bakery
        * with the arguments:
            | --fakename |
        When I execute the command
        Then The command fails
        * an error message is shown
        * usage is shown

    Scenario: bakery with unknown command
        Given I call bakery
        * with the arguments:
            | nope |
        When I execute the command
        Then The command fails
        * an error message is shown
        * usage is shown
        * the output includes:
            | No such command 'nope' |

    Scenario: bakery with unknown option
        Given I call bakery
        * with the arguments:
            | --planet | mars |
        When I execute the command
        Then The command fails
        * an error message is shown
        * usage is shown
        * the output includes:
            | No such option: --planet |
