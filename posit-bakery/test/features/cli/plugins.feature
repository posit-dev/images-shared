@functional
Feature: plugins

    Scenario Outline: Bakery discovers the builtin plugin and exposes its command group
        Given I call bakery <plugin>
        * with the arguments:
            | --help |
        When I execute the command
        Then The command succeeds
        * help is shown
        * the stdout output includes:
            | Usage: bakery <plugin> |

        Examples:
            | plugin     |
            | dgoss      |
            | hadolint   |
            | wizcli     |
            | imagetools |
