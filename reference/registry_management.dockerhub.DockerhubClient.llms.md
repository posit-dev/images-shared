# registry_management.dockerhub.DockerhubClient

# registry_management.dockerhub.DockerhubClient

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/registry_management/dockerhub/api.py#L8-L161)

``` python
registry_management.dockerhub.DockerhubClient()
```

## Attributes

| Name                    | Description                     |
|-------------------------|---------------------------------|
| [BASE_URL](#BASE_URL)   | str(object=’’) -\> str          |
| [ENDPOINTS](#ENDPOINTS) | dict() -\> new empty dictionary |

### BASE_URL

str(object=’’) -\> str

`BASE_URL``=``"https://hub.docker.com/v2/"`

str(bytes_or_buffer\[, encoding\[, errors\]\]) -\> str

Create a new string object from the given object. If encoding or errors is specified, then the object must expose a data buffer that will be decoded using the given encoding and error handler. Otherwise, returns the result of object.\_\_str\_\_() (if defined) or repr(object). encoding defaults to sys.getdefaultencoding(). errors defaults to ‘strict’.

### ENDPOINTS

dict() -\> new empty dictionary

`ENDPOINTS``=``{`  
`    ``"auth"``: ``"auth/token"``,`  
`    ``"repositories"``: ``"namespaces/{namespace}/repositories"``,`  
`    ``"repository"``: ``"namespaces/{namespace}/repositories/{repository}"``,`  
`    ``"tags"``: ``"namespaces/{namespace}/repositories/{repository}/tags"``,`  
`    ``"tag"``: ``"namespaces/{namespace}/repositories/{repository}/tags/{tag}"``,`  
`}`  

dict(mapping) -\> new dictionary initialized from a mapping object’s (key, value) pairs dict(iterable) -\> new dictionary initialized as if via: d = {} for k, v in iterable: d\[k\] = v dict(\*\*kwargs) -\> new dictionary initialized with the name=value pairs in the keyword argument list. For example: dict(one=1, two=2)

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
