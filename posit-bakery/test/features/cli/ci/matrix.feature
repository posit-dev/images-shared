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

    Scenario: Filtering the CI matrix by image name excludes non-matching images
        Given I call bakery ci matrix
        * in the merge-multi-image context
        * with the arguments:
            | test-alpha$ |
        When I execute the command
        Then The command succeeds
        * the matrix matches testdata ci/matrix/merge-multi-image/image_name_filter.json

    Scenario: A version-dir change builds only that version
        Given I call bakery ci matrix
        * in the changeset context
        * with changed files in changed-files.txt:
            | app/1.0.0/Containerfile.ubuntu2204.std |
        When I execute the command
        Then The command succeeds
        * the matrix matches testdata ci/matrix/changeset/version_only.json

    Scenario: A Markdown-only change yields an empty matrix
        Given I call bakery ci matrix
        * in the changeset context
        * with changed files in changed-files.txt:
            | README.md |
        When I execute the command
        Then The command succeeds
        * the matrix matches testdata ci/matrix/changeset/empty.json

    Scenario: A bakery.yaml change falls back to the full matrix
        Given I call bakery ci matrix
        * in the changeset context
        * with changed files in changed-files.txt:
            | bakery.yaml |
        When I execute the command
        Then The command succeeds
        * the matrix matches testdata ci/matrix/changeset/full.json
