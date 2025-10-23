@functional
Feature: remove version

    Scenario: Removing an existing version from an image succeeds
        Given I call bakery remove version
        * in a temp basic context
        * with the arguments:
            | test-image |
            | 1.0.0 |
        When I execute the command
        Then The command succeeds
        * the version '1.0.0' in the 'test-image' image should not exist in the bakery config
        * the path '1.0.0' should not exist in the 'test-image' image path
        * the stderr output includes:
            | Successfully removed version |
            | '1.0.0' |
            | from image |
            | 'test-image' |

    Scenario: Removing a non-existent version fails
        Given I call bakery remove version
        * in a temp basic context
        * with the arguments:
            | test-image |
            | 2.0.0 |
        When I execute the command
        Then The command exits with code 1
        * the stderr output includes:
            | Failed to remove version |
            | '2.0.0' |
            | from image |
            | 'test-image' |

    Scenario: Removing a version from a non-existent image fails
        Given I call bakery remove version
        * in a temp basic context
        * with the arguments:
            | non-existent-image |
            | 1.0.0 |
        When I execute the command
        Then The command exits with code 1
        * the stderr output includes:
            | Failed to remove version |
            | '1.0.0' |
            | 'non-existent-image' |
