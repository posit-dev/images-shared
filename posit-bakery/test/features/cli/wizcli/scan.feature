@functional
Feature: wizcli scan

    Scenario: Running wizcli scan with no matching targets fails
        Given I call bakery wizcli scan
        * in a temp basic context
        * with the arguments:
            | --image-name | nonexistent |
        When I execute the command
        Then The command fails
        * the stderr output includes:
            | No image targets to scan |

    Scenario: Running wizcli tag without a metadata file fails
        Given I call bakery wizcli tag
        * in a temp basic context
        When I execute the command
        Then The command fails
        * an error message is shown
        * usage is shown
        * the stderr output includes:
            | --metadata-file |

    Scenario: Bakery shows wizcli scan help
        Given I call bakery wizcli scan
        * with the arguments:
            | --help |
        When I execute the command
        Then The command succeeds
        * help is shown
        * the stdout output includes:
            | WizCLI Options |
