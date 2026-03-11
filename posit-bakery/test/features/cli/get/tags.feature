@functional
Feature: get tags

    Scenario: Getting tags for the barebones suite
        Given I call bakery get tags
        * in the barebones context
        When I execute the command
        Then The command succeeds
        * the tags match testdata get/tags/barebones/default.json

    Scenario: Getting tags for the basic suite
        Given I call bakery get tags
        * in the basic context
        When I execute the command
        Then The command succeeds
        * the tags match testdata get/tags/basic/default.json

    Scenario: Getting tags for the multiplatform suite
        Given I call bakery get tags
        * in the multiplatform context
        When I execute the command
        Then The command succeeds
        * the tags match testdata get/tags/multiplatform/default.json
