@functional
Feature: bakery new

    Scenario: I create a new image
        Given I run bakery "new"
        * with the "debug" flag
        * with the arguments "new_image"
        * with the "image" option set to "test_image"
        When I execute the command
