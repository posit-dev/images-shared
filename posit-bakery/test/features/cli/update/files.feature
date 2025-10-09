@functional
Feature: update files

  Scenario: Updating files from templates
      Given I call bakery update files
      * in a temp with-macros context
      * with the 'test-image/1.0.0' path removed
      * with the arguments:
          | --image-name |
          | test-image |
          | --image-version |
          | 1.0.0 |
      When I execute the command
      Then The command succeeds
      * the image "test-image" exists
      * the version "1.0.0" exists
      * the default rendered templates exist
      * the stderr output includes:
          | Files rendered successfully |
