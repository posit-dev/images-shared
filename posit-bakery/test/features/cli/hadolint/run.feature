@functional
Feature: hadolint run

    @image_build
    Scenario: Linting basic images writes results
        Given I call bakery hadolint run
        * in a temp basic context
        When I execute the command
        Then The command succeeds
        * the stderr output includes:
            | Linting completed |
        * the context includes files:
            | results/hadolint/test-image/test-image-1-0-0-minimal-ubuntu-22-04.json  |
            | results/hadolint/test-image/test-image-1-0-0-standard-ubuntu-22-04.json |

    @image_build
    Scenario: A stricter failure threshold fails on warnings
        Given I call bakery hadolint run
        * in a temp basic context
        * with the arguments:
            | --failure-threshold | warning |
        When I execute the command
        Then The command fails

    Scenario: Running hadolint with no matching targets fails
        Given I call bakery hadolint run
        * in a temp basic context
        * with the arguments:
            | --image-name | nonexistent |
        When I execute the command
        Then The command fails
        * the stderr output includes:
            | No image targets to |
