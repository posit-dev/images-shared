@functional
Feature: bakery plan

    Scenario: bakery plan
        Given I call bakery "plan"
        * with the basic context
        When I execute the command
        Then The command succeeds
        * the output is JSON
