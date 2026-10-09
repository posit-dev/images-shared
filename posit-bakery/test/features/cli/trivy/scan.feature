@functional
Feature: trivy

    @image_build @slow
    Scenario: Running trivy scan against basic images
        Given I call bakery build
        * in a temp basic context
        When I execute the command
        Then The command succeeds

        Given I call bakery trivy scan
        * in a temp basic context
        When I execute the command
        Then The command succeeds
        * the context includes files:
            | results/trivy/test-image/test-image-1-0-0-minimal-ubuntu-22-04.sarif |
            | results/trivy/test-image/test-image-1-0-0-standard-ubuntu-22-04.sarif |
        * the basic images are removed

    Scenario: Running trivy scan with no matching targets fails
        Given I call bakery trivy scan
        * in a temp basic context
        * with the arguments:
            | --image-name | nonexistent |
        When I execute the command
        Then The command fails
        * the stderr output includes:
            | No image targets to scan |

    Scenario: Bakery shows trivy scan help
        Given I call bakery trivy scan
        * with the arguments:
            | --help |
        When I execute the command
        Then The command succeeds
        * help is shown
        * the stdout output includes:
            | Trivy Options |
