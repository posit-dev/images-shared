# config.ImageVariant

# config.ImageVariant

Model representing a variant of an image.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/variant.py#L13-L79)

``` python
config.ImageVariant()
```

## Methods

| Name | Description |
|----|----|
| [get_tool_option()](#get_tool_option) | Returns tool options for this image variant. |

### get_tool_option()

Returns tool options for this image variant.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/variant.py#L51-L79)

``` python
get_tool_option(tool, merge_with_parent=True)
```

By default, the tool option for the variant will be merged with the parent image’s tool options if they exist. Tool options set to non-defaults in the variant will take precedence over those in the parent.

#### Parameters

`tool``:`` ``str`  
The name of the tool to get options for.

#### Returns

` ``ToolOptions | None`  
The ToolOptions object for the specified tool, or None if not found.

Back to top
