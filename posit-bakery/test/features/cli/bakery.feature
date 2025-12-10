@functional
Feature: bakery

    Scenario: Bakery shows a help message when --help is passed
        Given I call bakery
        * with the arguments:
            | --help |
        When I execute the command
        Then The command succeeds
        * help is shown

    # Exit code is expected to be 2 going forward per https://github.com/fastapi/typer/pull/1240
    Scenario: Bakery shows a help message when no commands or arguments are given
        Given I call bakery
        When I execute the command
        Then The command exits with code 2
        * help is shown

    Scenario: Bakery shows an error message for a bad flag
        Given I call bakery
        * with the arguments:
            | --fakename |
        When I execute the command
        Then The command fails
        * an error message is shown
        * usage is shown

    Scenario: Bakery shows an error message for a bad command
        Given I call bakery
        * with the arguments:
            | nope |
        When I execute the command
        Then The command fails
        * an error message is shown
        * usage is shown
        * the stderr output includes:
            | No such command 'nope' |

    Scenario: Bakery shows an error message for multiple bad options
        Given I call bakery
        * with the arguments:
            | --planet | mars |
        When I execute the command
        Then The command fails
        * an error message is shown
        * usage is shown
        * the stderr output includes:
            | No such option: --planet |

    Scenario: Bakery shows its version for --version and exits
        Given I call bakery version
        When I execute the command
        Then The command succeeds
        * the version is shown
