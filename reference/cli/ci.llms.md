# bakery ci

# bakery ci

Construct a CI matrix from the project.

``` bash
bakery ci COMMAND [ARGS]...
```

    Usage: bakery ci [OPTIONS] COMMAND [ARGS]...

      Construct a CI matrix from the project.

    Options:
      --help  Show this message and exit.

    Commands:
      matrix   Generates a JSON matrix of image versions for CI workflows to...
      merge    Alias for `bakery ci publish`.
      publish  Publish multi-platform images by composing oras index-create →...
      readme   Push image READMEs to Docker Hub.

## Commands

`matrix`  
[Generates a JSON matrix of image versions for CI workflows to consume](../../reference/cli/ci/matrix.llms.md)

`merge`  
[Alias for `bakery ci publish`.](../../reference/cli/ci/merge.llms.md)

`publish`  
[Publish multi-platform images by composing oras index-create → soci-convert → oras index-copy.](../../reference/cli/ci/publish.llms.md)

`readme`  
[Push image READMEs to Docker Hub.](../../reference/cli/ci/readme.llms.md)

Back to top
