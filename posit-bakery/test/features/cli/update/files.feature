@functional
Feature: update files

  Scenario: Updating version files from templates
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
          | Files updated successfully |

  Scenario: Updating matrix files from templates
      Given I call bakery update files
      * in a temp matrix context
      * with the 'test-matrix/matrix' path removed
      * with the arguments:
          | --image-name |
          | test-matrix |
      When I execute the command
      Then The command succeeds
      * the image "test-matrix" exists
      * the default matrix rendered templates exist
      * the stderr output includes:
          | Files updated successfully |

  Scenario: Updating files without a scope fails
      Given I call bakery update files
      * in a temp with-macros context
      When I execute the command
      Then The command fails
      * the stderr output includes:
          | No scope specified |

  Scenario: Updating all files with --all
      Given I call bakery update files
      * in a temp with-macros context
      * with the 'test-image/1.0.0' path removed
      * with the arguments:
          | --all |
      When I execute the command
      Then The command succeeds
      * the image "test-image" exists
      * the version "1.0.0" exists
      * the default rendered templates exist
      * the stderr output includes:
          | Files updated successfully |
