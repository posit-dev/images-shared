@functional
Feature: create project

  Scenario: Creating a new project when the project already exists
    Given I call bakery create project
    * in the basic context
    When I execute the command
    Then The command exits with code 1
    * the stderr output includes:
        | Project already exists |

  Scenario: Creating a new project
    Given I call bakery create project
    * in a temp directory
    When I execute the command
    Then The command succeeds
    * bakery.yaml exists
    * the stderr output includes:
        | Project initialized in |
