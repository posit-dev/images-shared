@functional
Feature: imagetools merge

    Scenario: Merging without a metadata file argument fails
        Given I call bakery imagetools merge
        * in a temp basic context
        When I execute the command
        Then The command fails
        * an error message is shown
        * usage is shown
        * the stderr output includes:
            | metadata_file |

    Scenario: Merging a missing metadata file fails
        Given I call bakery imagetools merge
        * in a temp basic context
        * with the arguments:
            | nope-metadata.json |
        When I execute the command
        Then The command fails
        * the log includes:
            | does not exist |
            | aborting merge |

    Scenario: Converting a missing metadata file to SOCI fails
        Given I call bakery imagetools soci-convert
        * in a temp basic context
        * with the arguments:
            | nope-metadata.json |
        When I execute the command
        Then The command fails
        * the log includes:
            | does not exist |

    Scenario: The hidden 'oras merge' alias still rejects a missing metadata file
        Given I call bakery oras merge
        * in a temp basic context
        * with the arguments:
            | nope-metadata.json |
        When I execute the command
        Then The command fails
        * the log includes:
            | does not exist |
