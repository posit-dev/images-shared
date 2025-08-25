@functional
Feature: create image

    Scenario: Creating a new image
        Given I call bakery create image
        * in a temp basic context
        * with the arguments:
            | brand-new-image |
        When I execute the command
        Then The command succeeds
        * the image "brand-new-image" exists
        * the default templates exist
        * the default base image is "docker.io/library/ubuntu:22.04"
        * the stderr output includes:
            | Successfully created image |
            | 'brand-new-image' |

    Scenario: Creating a new image with a custom base image defined
        Given I call bakery create image
        * in a temp basic context
        * with the arguments:
            | --base-image |
            | registry/base-image:1.0.3 |
            | custom-new-image |
        When I execute the command
        Then The command succeeds
        * the image "custom-new-image" exists
        * the default templates exist
        * the default base image is "registry/base-image:1.0.3"
        * the stderr output includes:
            | Successfully created image |
            | 'custom-new-image' |

    Scenario: Creating a new image with a custom subpath
        Given I call bakery create image
        * in a temp basic context
        * with the arguments:
            | new-image | --subpath | new/image |
        When I execute the command
        Then The command succeeds
        * the image "new-image" exists in the "new/image" subpath
        * the default templates exist in the "new/image" subpath
        * the default base image is "docker.io/library/ubuntu:22.04" in the "new/image" subpath
        * the stderr output includes:
            | Successfully created image |
            | 'new-image' |

    Scenario: Creating a duplicate image name fails
        Given I call bakery create image
        * in a temp basic context
        * with the arguments:
            | test-image |
        When I execute the command
        Then The command fails
