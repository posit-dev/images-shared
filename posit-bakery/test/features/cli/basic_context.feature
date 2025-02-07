@functional
Feature: Basic Context

    Scenario: bakery build --plan
        Given I call bakery "build"
        * in a temp basic context
        * with the arguments:
            | --plan |
        When I execute the command
        Then The command succeeds
        * the bake plan is valid

    Scenario: bakery build --plan with git commit
        Given I call bakery "build"
        * in the basic context
        * with the arguments:
            | --plan |
        When I execute the command
        Then The command succeeds
        * the bake plan is valid
        * the targets include the commit hash

    Scenario: bakery create image
        Given I call bakery "create" "image"
        * in a temp basic context
        * with the arguments:
            | --base-image |
            | registry/base-image:1.0.3 |
            | brand-new-image |
        When I execute the command
        Then The command succeeds
        * the image "brand-new-image" exists
        * the default templates exist
        * the default base image is "registry/base-image:1.0.3"
        * the stderr output includes:
            | Successfully created image 'brand-new-image' |

    Scenario: bakery create image exists
        Given I call bakery "create" "image"
        * in a temp basic context
        * with the arguments:
            | test-image |
        When I execute the command
        Then The command fails

    Scenario: bakery create version
        Given I call bakery "create" "version"
        * in a temp basic context
        * with the arguments:
            | test-image |
            | 1.1.0 |
        When I execute the command
        Then The command succeeds
        * the image "test-image" exists
        * the version "1.1.0" exists
        * the default rendered templates exist
        * the stderr output includes:
            | Successfully created version 'test-image/1.1.0' |

    @slow
    Scenario: bakery run dgoss
        Given I call bakery "build"
        * in a temp basic context
        * with the arguments:
            | --load |
        When I execute the command
        Then The command succeeds

        Given I call bakery "run" "dgoss"
        * in a temp basic context
        When I execute the command
        Then The command succeeds
