@functional
Feature: bakery new

    @skip  # Need to fix bakery new first
    Scenario: bakery new
        Given I run bakery "new"
        * with the arguments "new_image"
        * with the "image" option set to "test_image"
        When I execute the command
