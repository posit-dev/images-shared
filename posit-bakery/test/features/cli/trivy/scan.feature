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
