@functional
Feature: Basic Context

    Scenario: bakery plan
        Given I call bakery "plan"
        * in a temp basic context
        When I execute the command
        Then The command succeeds
        * the bake plan is valid

    Scenario: bakery plan with git commit
        Given I call bakery "plan"
        * in the basic context
        When I execute the command
        Then The command succeeds
        * the bake plan is valid
        * the targets include the commit hash

    Scenario: bakery new
        Given I call bakery "new"
        * in a temp basic context
        * with the arguments:
            | --image-base | registry/base-image:1.0.3 |
            | brand-new-image | |
        When I execute the command
        Then The command succeeds
        * the image "brand-new-image" exists
        * the default templates exist
        * the default base image is "registry/base-image:1.0.3"

    Scenario: bakery new image exists
        Given I call bakery "new"
        * in a temp basic context
        * with the arguments:
            | test-image |
        When I execute the command
        Then The command fails

    Scenario: bakery render
        Given I call bakery "render"
        * in a temp basic context
        * with the arguments:
            | test-image |
            | 0.9.9 |
        When I execute the command
        Then The command succeeds
        * the image "test-image" exists
        * the version "0.9.9" exists
        * the default rendered templates exist
