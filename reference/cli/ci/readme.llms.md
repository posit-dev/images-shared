# bakery ci readme

# bakery ci readme

Push image READMEs to Docker Hub.

``` bash
bakery ci readme [OPTIONS]
```

Pushes the README.md from each image directory to the corresponding Docker Hub repository description. Only pushes for eligible images: latest versions, matrix versions, and non-development versions with Docker Hub registries configured.

Requires DOCKER_HUB_README_USERNAME and DOCKER_HUB_README_PASSWORD environment variables to be set with a Personal Access Token (PAT). Organization Access Tokens cannot update repository descriptions.

    Usage: bakery ci readme [OPTIONS]

      Push image READMEs to Docker Hub.

      Pushes the README.md from each image directory to the corresponding Docker
      Hub repository description. Only pushes for eligible images: latest
      versions, matrix versions, and non-development versions with Docker Hub
      registries configured.

      Requires DOCKER_HUB_README_USERNAME and DOCKER_HUB_README_PASSWORD
      environment variables to be set with a Personal Access Token (PAT).
      Organization Access Tokens cannot update repository descriptions.

    Options:
      --context DIRECTORY             The root path to use. Defaults to the
                                      current working directory where invoked.
                                      [default: (.)]
      --dev-versions [include|exclude|only]
                                      Include or exclude development versions
                                      defined in config.  [default: include]
      --dev-channel [release|preview|daily]
                                      Filter development versions to a specific
                                      release channel.
      --matrix-versions [include|exclude|only]
                                      Include or exclude versions defined in image
                                      matrix.  [default: include]
      -v, --verbose                   Enable debug logging
      -q, --quiet                     Supress all output except errors
      --help                          Show this message and exit.

## Options

`--context``:`` ``DIRECTORY`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory where invoked.

`--dev-versions``:`` ``CHOICE`` ``=`` ``DevVersionInclusionEnum.INCLUDE`  
Include or exclude development versions defined in config.

`--dev-channel``:`` ``CHOICE`  
Filter development versions to a specific release channel.

`--matrix-versions``:`` ``CHOICE`` ``=`` ``MatrixVersionInclusionEnum.INCLUDE`  
Include or exclude versions defined in image matrix.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

Back to top
