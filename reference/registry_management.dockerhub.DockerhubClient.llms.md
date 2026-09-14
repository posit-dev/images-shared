# registry_management.dockerhub.DockerhubClient

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/registry_management/dockerhub/api.py#L8-L161)

``` python
registry_management.dockerhub.DockerhubClient(identifier=None, secret=None)
```

## Methods

| Name | Description |
|----|----|
| [update_full_description()](#update_full_description) | Update the full description (README) of a Docker Hub repository. |

### update_full_description()

Update the full description (README) of a Docker Hub repository.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/registry_management/dockerhub/api.py#L138-L161)

``` python
update_full_description(namespace=None, repository=None, full_description=None)
```

#### Parameters

`namespace``:`` ``str | None`` ``=`` ``None`  
The namespace (organization or user) of the repository.

`repository``:`` ``str | None`` ``=`` ``None`  
The name of the repository.

`full_description``:`` ``str | None`` ``=`` ``None`  
The full description content (typically README.md contents). Docker Hub limits this to 25,000 bytes.

#### Returns

` ``dict`  
The updated repository data from Docker Hub.

Back to top
