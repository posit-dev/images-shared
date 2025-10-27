@functional
Feature: get images

    Scenario: Get images for the basic project
      Given I call bakery get images
      * in the basic context
      When I execute the command
      Then The command succeeds
      * the stdout output includes:
      | test-image |
