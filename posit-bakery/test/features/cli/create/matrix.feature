@functional
Feature: create matrix

    Scenario: Creating a new matrix fails without any dependencies or values passed
        Given I call bakery create matrix
        * in a temp basic context
        * with a new image named "test-matrix"
        * with the arguments:
            | test-matrix |
        When I execute the command
        Then The command fails
        * the image "test-matrix" exists
        * the stderr output includes:
            | Failed to create matrix for image |
            | 'test-matrix' |

    Scenario: Creating a new matrix
        Given I call bakery create matrix
        * in a temp basic context
        * with a new image named "test-matrix"
        * with the arguments:
            | test-matrix |
            | --dependency-constraint |
            | {"dependency": "R", "constraint": {"latest": true}} |
            | --dependency |
            | {"dependency": "python", "version": ["3.14.1"]} |
        When I execute the command
        Then The command succeeds
        * the image "test-matrix" exists
        * the context includes files:
          | test-matrix/matrix/Containerfile |
        * the stderr output includes:
            | Successfully created matrix for image |
            | 'test-matrix' |
