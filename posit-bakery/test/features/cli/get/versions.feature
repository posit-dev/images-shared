@functional
Feature: get versions

    Scenario: Get images for the basic project
      Given I call bakery get versions
      * in the basic context
      * with the arguments:
      | test-image |
      When I execute the command
      Then The command succeeds
      * the stdout output includes:
      | 1.0.0 |
