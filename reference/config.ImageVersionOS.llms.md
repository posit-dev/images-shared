# config.ImageVersionOS

# config.ImageVersionOS

Model representing a supported operating system for an image version.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/version_os.py#L15-L133)

``` python
config.ImageVersionOS()
```

## Methods

| Name | Description |
|----|----|
| [\_\_eq\_\_()](#__eq__) | Equality check for ImageVersionOS based on name. |
| [populate_build_os()](#populate_build_os) | Populates the build_os field based on the name field. If the OS cannot be determined, it defaults to unknown. |
| [serialize_platforms()](#serialize_platforms) | Serialize the platforms field to a list of strings for YAML output. |

### \_\_eq\_\_()

Equality check for ImageVersionOS based on name.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/version_os.py#L74-L81)

``` python
__eq__(other)
```

#### Parameters

`other`  
The other object to compare against.

### populate_build_os()

Populates the build_os field based on the name field. If the OS cannot be determined, it defaults to unknown.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/version_os.py#L83-L128)

``` python
populate_build_os(value, info)
```

### serialize_platforms()

Serialize the platforms field to a list of strings for YAML output.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/version_os.py#L130-L133)

``` python
serialize_platforms(platforms)
```

Back to top
