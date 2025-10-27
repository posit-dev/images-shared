@functional
Feature: get registries

    Scenario: Get registries with no filters prints all registries for the barebones project
      Given I call bakery get registries
      * in the barebones context
      When I execute the command
      Then The command succeeds
      * the stdout output includes:
      | ghcr.io/posit-dev/scratch |

    Scenario: Get registries with no filters prints all registries for the basic project
      Given I call bakery get registries
      * in the basic context
      When I execute the command
      Then The command succeeds
      * the stdout output includes:
      | docker.io/posit/test-image |
      | ghcr.io/posit-dev/test-image |

    Scenario: Get registries with filter prints only matching registries in the project
      Given I call bakery get registries
      * in the basic context
      * with the arguments:
          | --pattern |
          # Do not quote the value below or it will not parse correctly.
          | ghcr.* |
      When I execute the command
      Then The command succeeds
      * the stdout output includes:
      | ghcr.io/posit-dev/test-image |
      * the stdout output does not include:
      | docker.io/posit/test-image |
