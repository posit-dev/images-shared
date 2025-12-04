@functional
Feature: merge

    Scenario: Merging multiplatform builds
        Given I call bakery ci merge *-metadata.json
        * in a temp multiplatform context
        * with testdata ci/merge/multiplatform copied to context
        * with image target merge method patched
        When I execute the command
        Then The command succeeds
        * the files read include:
            | amd64-metadata.json |
            | arm64-metadata.json |
        * 6 targets are found in the metadata
        * the merge calls include:
            | cripittwood.azurecr.io/posit/test-multi/tmp:latest@sha256:f5d7d95a3801d05f91db1fa7b5bba9fdb3d5babc0332c56f0cca25407c93a2f1 |                                                                                                                            |
            | cripittwood.azurecr.io/posit/test-multi/tmp:latest@sha256:22adb0b3d07e78916da03c81b899d5ded4aaff8098d40a9b8cb071c8c0f3a4a2 | cripittwood.azurecr.io/posit/test-multi/tmp:latest@sha256:b0f70c272157281f3e70fcd1d890d6927a9268f4bd315e6d7cba677182bd6098 |
            | cripittwood.azurecr.io/posit/test-multi/tmp:latest@sha256:f31fb59b841be3502be62d4e85696b002204a94821839ce2e8e2fa7c26eb232a |                                                                                                                            |
            | cripittwood.azurecr.io/posit/test-multi/tmp:latest@sha256:e0ee4e80f5d1b04dd103d19a7db1198c0b8bd214ed040b87d74521f2dcd6ea8e | cripittwood.azurecr.io/posit/test-multi/tmp:latest@sha256:415b48b2fcc903f194b20e48cdbd2c76e2f8127c2453f8b18e5512973186dde0 |
