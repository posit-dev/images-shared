@functional
Feature: create version

    Scenario: Creating a new version
        Given I call bakery create version
        * in a temp basic context
        * with the arguments:
            | test-image |
            | 1.1.0 |
        When I execute the command
        Then The command succeeds
        * the image "test-image" exists
        * the version "1.1.0" exists
        * the default rendered templates exist
        * the stderr output includes:
            | Successfully created version |
            | 'test-image/1.1.0' |

    Scenario: Creating a new version with extra values
        Given I call bakery create version
        * in a temp basic context
        * with the arguments:
            | test-image |
            | 1.1.0 |
            | --value |
            | extra_key=extra_value |
        When I execute the command
        Then The command succeeds
        * the image "test-image" exists
        * the version "1.1.0" exists
        * the default rendered templates exist
        * bakery.yaml contains:
            | values: |
            | extra_key: extra_value |
        * the stderr output includes:
            | Successfully created version |
            | 'test-image/1.1.0' |

    Scenario: Creating a new version with a custom subpath
        Given I call bakery create version
        * in a temp basic context
        * with the arguments:
            | test-image |
            | 1.1.0 |
            | --subpath |
            | 1.1 |
        When I execute the command
        Then The command succeeds
        * the image "test-image" exists
        * the version "1.1.0" exists in the "1.1" subpath
        * the default rendered templates exist in the "1.1" subpath
        * the stderr output includes:
            | Successfully created version |
            | 'test-image/1.1.0' |

    Scenario: Creating a new version from templates with macros
        Given I call bakery create version
        * in a temp with-macros context
        * with the arguments:
            | test-image |
            | 1.1.0 |
        When I execute the command
        Then The command succeeds
        * the image "test-image" exists
        * the version "1.1.0" exists
        * the default rendered templates exist
        * the stderr output includes:
            | Successfully created version |
            | 'test-image/1.1.0' |

    Scenario: Creating a duplicate version fails without --force
        Given I call bakery create version
        * in a temp basic context
        * with the arguments:
            | test-image |
            | 1.0.0 |
        When I execute the command
        Then The command exits with code 1
        * the image "test-image" exists
        * the version "1.0.0" exists
        * the default rendered templates exist
        * the stderr output includes:
            | Failed to create version |
            | 'test-image/1.0.0' |

    Scenario: Creating a duplicate version works with --force
        Given I call bakery create version
        * in a temp basic context
        * with the arguments:
            | test-image |
            | 1.0.0 |
            | --force |
        When I execute the command
        Then The command succeeds
        * the image "test-image" exists
        * the version "1.0.0" exists
        * the default rendered templates exist
        * the stderr output includes:
            | Successfully created version |
            | 'test-image/1.0.0' |
