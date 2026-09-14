# registry_management.ghcr.GHCRClient

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/registry_management/ghcr/api.py#L22-L96)

``` python
registry_management.ghcr.GHCRClient(
    organization, token=os.getenv("GITHUB_TOKEN")
)
```

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
