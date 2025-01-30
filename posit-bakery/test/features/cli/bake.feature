@functional
Feature: bakery plan

    Scenario: bakery plan
        Given I call bakery "plan"
        * in a temp basic context
        When I execute the command
        Then The command succeeds
        * the plan is valid

    Scenario: bakery plan with git commit
        Given I call bakery "plan"
        * in the basic context
        When I execute the command
        Then The command succeeds
        * the plan is valid
        * the targets include the commit hash
