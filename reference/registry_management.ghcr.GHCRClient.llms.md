# registry_management.ghcr.GHCRClient

# registry_management.ghcr.GHCRClient

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/registry_management/ghcr/api.py#L22-L96)

``` python
registry_management.ghcr.GHCRClient()
```

## Attributes

| Name                    | Description                     |
|-------------------------|---------------------------------|
| [ENDPOINTS](#ENDPOINTS) | dict() -\> new empty dictionary |

### ENDPOINTS

dict() -\> new empty dictionary

`ENDPOINTS``=``{`  
`    ``"package"``: ``"/orgs/{organization}/packages/container/{package}"``,`  
`    ``"package_versions"``: ``"/orgs/{organization}/packages/container/{package}/versions"``,`  
`}`  

dict(mapping) -\> new dictionary initialized from a mapping object’s (key, value) pairs dict(iterable) -\> new dictionary initialized as if via: d = {} for k, v in iterable: d\[k\] = v dict(\*\*kwargs) -\> new dictionary initialized with the name=value pairs in the keyword argument list. For example: dict(one=1, two=2)

## Methods

| Name                          | Description               |
|-------------------------------|---------------------------|
| [get_package()](#get_package) | Get details on a package. |

### get_package()

Get details on a package.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/registry_management/ghcr/api.py#L40-L48)

``` python
get_package(organization, package)
```

Back to top
