@functional
Feature: bakery plan

    Scenario: bakery plan
        Given I call bakery "plan"
        * with a temp basic context
        When I execute the command
        Then The command succeeds
        * the output is valid JSON

    Scenario: bakery plan with git commit
        Given I call bakery "plan"
        * with the basic context
        When I execute the command
        Then The command succeeds
        * the output is valid JSON
        * the targets include the commit hash
