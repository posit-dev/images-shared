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

    Scenario: Filtering the CI matrix to a matching image version
        Given I call bakery ci matrix
        * in the basic context
        * with the arguments:
            | --image-version | 1.0.0 |
        When I execute the command
        Then The command succeeds
        * the matrix matches testdata ci/matrix/basic/image_version_match.json

    Scenario: Filtering the CI matrix to an unknown image version fails loudly
        Given I call bakery ci matrix
        * in the basic context
        * with the arguments:
            | --image-version | 9.9.9 |
        When I execute the command
        Then The command fails
