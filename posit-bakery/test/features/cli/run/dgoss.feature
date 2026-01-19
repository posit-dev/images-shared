@functional
Feature: dgoss

    @slow
    @xdist-build
    Scenario: Running dgoss tests against basic images
        Given I call bakery build
        * in a temp basic context
        When I execute the command
        Then The command succeeds

        Given I call bakery run dgoss
        * in a temp basic context
        When I execute the command
        Then The command succeeds
        * the stderr output includes:
            | Tests completed |
        * the context includes files:
            | results/dgoss/test-image/test-image-1-0-0-minimal-ubuntu-22-04.json |
            | results/dgoss/test-image/test-image-1-0-0-standard-ubuntu-22-04.json |
        * the basic images are removed

    @slow
    @xdist-build
    Scenario: Running dgoss tests against with-macros images
        Given I call bakery build
        * in a temp with-macros context
        When I execute the command
        Then The command succeeds

        Given I call bakery run dgoss
        * in a temp with-macros context
        When I execute the command
        Then The command succeeds
        * the stderr output includes:
            | Tests completed |
        * the context includes files:
            | results/dgoss/test-image/test-image-1-0-0-minimal-ubuntu-22-04.json |
            | results/dgoss/test-image/test-image-1-0-0-standard-ubuntu-22-04.json |
        * the with-macros images are removed

    @slow
    @xdist-build
    Scenario: Running dgoss tests against matrix images
        Given I call bakery build
        * in a temp matrix context
        When I execute the command
        Then The command succeeds

        Given I call bakery run dgoss
        * in a temp with-macros context
        When I execute the command
        Then The command succeeds
        * the stderr output includes:
            | Tests completed |
        * the matrix images are removed
