@functional
Feature: remove image

    Scenario: Removing an existing image
        Given I call bakery remove image
        * in a temp basic context
        * with the arguments:
            | test-image |
        When I execute the command
        Then The command succeeds
        * the image 'test-image' should not exist in the bakery config
        * the path 'test-image' should not exist in the bakery context
        * the stderr output includes:
            | Successfully removed image |
            | 'test-image' |

    Scenario: Removing a non-existent image fails
        Given I call bakery remove image
        * in a temp basic context
        * with the arguments:
            | non-existent-image |
        When I execute the command
        Then The command exits with code 1
        * the stderr output includes:
            | Failed to remove image |
            | 'non-existent-image' |
