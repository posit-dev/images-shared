# registry_management.dockerhub.push_readmes()

# registry_management.dockerhub.push_readmes()

Push READMEs to Docker Hub for eligible image targets.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/registry_management/dockerhub/readme.py#L113-L185)

``` python
registry_management.dockerhub.push_readmes(targets)
```

Pushes the README.md from each image directory to the corresponding Docker Hub repository description. Only pushes for targets that are:

- Marked as latest, or a matrix version
- Not a development version
- Have Docker Hub registry tags

Pushes once per Docker Hub repository, regardless of how many targets share it.

Requires DOCKER_HUB_README_USERNAME and DOCKER_HUB_README_PASSWORD environment variables to be set. Skips gracefully if credentials are not configured. Raises on authentication or push failures.

## Parameters

`targets``:`` ``list[ImageTarget]`  
List of image targets to evaluate.

## Returns

` ``int`  
Number of READMEs pushed.

## Raises

` ``ValueError`  
If one or more eligible READMEs exceed Docker Hub’s length limit.

` ``RuntimeError`  
If one or more README pushes fail.

Back to top
