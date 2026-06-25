# image.BakePlan

# image.BakePlan

Represents a JSON bake plan for building Docker images using Docker Bake.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/bake/bake.py#L159-L297)

``` python
image.BakePlan()
```

## Attributes

| Name | Description |
|----|----|
| [bake_file](#bake_file) | Return the path to the bake file in the context directory. |

### bake_file

Return the path to the bake file in the context directory.

`bake_file``:`` ``Path`

## Methods

| Name | Description |
|----|----|
| [build()](#build) | Run the bake plan to build all targets. |
| [from_image_targets()](#from_image_targets) | Create a BakePlan from a list of ImageTarget objects. |
| [remove()](#remove) | Delete the bake plan file if it exists. |
| [update_groups()](#update_groups) | Update the default, image name, and image variant groups with the given UID. |
| [write()](#write) | Write the bake plan to a file in the context directory. |

### build()

Run the bake plan to build all targets.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/bake/bake.py#L256-L297)

``` python
build(
    load=True,
    push=False,
    pull=False,
    cache=True,
    cache_from=None,
    cache_to=None,
    platforms=None,
    set_opts=None,
    clean_bakefile=True
)
```

### from_image_targets()

Create a BakePlan from a list of ImageTarget objects.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/bake/bake.py#L197-L227)

``` python
from_image_targets(context, image_targets, platforms=None, push=False)
```

#### Parameters

`context``:`` ``Path`  
The absolute path to the build context directory.

`image_targets``:`` ``list[ImageTarget]`  
A list of ImageTarget objects to include in the bake plan.

`platforms``:`` ``list[str] | None`` ``=`` ``None`  
Optional platform override (e.g., from CLI –platform flag). When provided, this takes precedence over each image target’s OS platform configuration for cache tag generation.

`push``:`` ``bool`` ``=`` ``False`  
If True, include cache-to in bake targets to push cache layers to the registry.

#### Returns

` ``BakePlan`  
A BakePlan object containing the context, groups, and targets.

### remove()

Delete the bake plan file if it exists.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/bake/bake.py#L234-L236)

``` python
remove()
```

### update_groups()

Update the default, image name, and image variant groups with the given UID.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/bake/bake.py#L171-L195)

``` python
update_groups(groups, uid, image_name, image_variant)
```

#### Parameters

`groups``:`` ``dict[str, BakeGroup]`  
The current groups of targets.

`uid``:`` ``str`  
The unique identifier for the target.

`image_name``:`` ``str`  
The name of the image.

`image_variant``:`` ``str`  
The variant of the image.

#### Returns

` ``dict[str, BakeGroup]`  
The updated groups with the new target added.

### write()

Write the bake plan to a file in the context directory.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/bake/bake.py#L229-L232)

``` python
write()
```

Back to top
