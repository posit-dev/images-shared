@functional
Feature: matrix

    Scenario: Generating a default CI matrix for the barebones suite
        Given I call bakery ci matrix
        * in the barebones context
        When I execute the command
        Then The command succeeds
        * the matrix matches testdata ci/matrix/barebones/default.json

    Scenario: Generating a default CI matrix for the basic suite
        Given I call bakery ci matrix
        * in the basic context
        When I execute the command
        Then The command succeeds
        * the matrix matches testdata ci/matrix/basic/default.json

    Scenario: Generating a default CI matrix for the barebones suite
        Given I call bakery ci matrix
        * in the multiplatform context
        When I execute the command
        Then The command succeeds
        * the matrix matches testdata ci/matrix/multiplatform/default.json

    Scenario: Generating a CI matrix for the multiplatform suite with platform excluded
        Given I call bakery ci matrix
        * in the multiplatform context
        * with the arguments:
            | --exclude | platform |
        When I execute the command
        Then The command succeeds
        * the matrix matches testdata ci/matrix/multiplatform/exclude_platform.json
