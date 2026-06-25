# config.BakeryConfigDocument

# config.BakeryConfigDocument

Model representation of the top-level bakery.yaml configuration document.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L76-L250)

``` python
config.BakeryConfigDocument()
```

## Attributes

| Name          | Description                                             |
|---------------|---------------------------------------------------------|
| [path](#path) | Returns the path to the bakery config parent directory. |

### path

Returns the path to the bakery config parent directory.

`path``:`` ``Path | None`

## Methods

| Name | Description |
|----|----|
| [check_image_duplicates()](#check_image_duplicates) | Ensures that there are no duplicate image names in the config. Raises an error if duplicates are found. |
| [check_images_not_empty()](#check_images_not_empty) | Ensures that the images list is not empty. Warns if no images are found. |
| [create_image_files_template()](#create_image_files_template) | Creates the necessary directories and files for a new image template. |
| [create_image_model()](#create_image_model) | Creates a new image directory and adds it to the config. |
| [deduplicate_registries()](#deduplicate_registries) | Ensures that the registries list is unique. Warns if duplicates are found. |
| [get_image()](#get_image) | Returns an image by name, or None if not found. |
| [resolve_parentage()](#resolve_parentage) | Sets the parent reference for the Repository and Image child objects. |

### check_image_duplicates()

Ensures that there are no duplicate image names in the config. Raises an error if duplicates are found.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L120-L138)

``` python
check_image_duplicates(images)
```

#### Parameters

`images``:`` ``list[Image]`  
List of Image objects to check for duplicates.

### check_images_not_empty()

Ensures that the images list is not empty. Warns if no images are found.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L109-L118)

``` python
check_images_not_empty(images)
```

#### Parameters

`images``:`` ``list[Image]`  
List of Image objects to check.

### create_image_files_template()

Creates the necessary directories and files for a new image template.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L163-L215)

``` python
create_image_files_template(image_path, image_name, base_tag)
```

This function does **NOT** create a new image model. Use `create_image_model` for that.

Creates the following structure: - image_path/ - template/ - Containerfile.{{ base_tag \| condensed }}.jinja2 - test/ - goss.yaml.jinja2 - deps/ - packages.txt.jinja2

#### Parameters

`image_path``:`` ``Path`  
The path to the image directory.

`image_name``:`` ``str`  
The name of the image.

`base_tag``:`` ``str`  
The base tag for the image to use in the `FROM` directive of the Containerfile template.

### create_image_model()

Creates a new image directory and adds it to the config.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L217-L250)

``` python
create_image_model(
    name,
    subpath=None,
    display_name=None,
    description=None,
    documentation_url=None
)
```

This function does **NOT** create the image files template. Use `create_image_files_template` for that.

#### Parameters

`name``:`` ``str`  
The name of the image to create.

`subpath``:`` ``str | None`` ``=`` ``None`  
Optional alternate subpath for the image.

`display_name``:`` ``str | None`` ``=`` ``None`  
Optional display name for the image. If not provided, the image name will be used.

`description``:`` ``str | None`` ``=`` ``None`  
Optional description for the image. Used in labels.

`documentation_url``:`` ``str | None`` ``=`` ``None`  
Optional URL for the image documentation. Used in labels.

#### Returns

` ``Image`  
The newly created Image model.

### deduplicate_registries()

Ensures that the registries list is unique. Warns if duplicates are found.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L96-L107)

``` python
deduplicate_registries(registries)
```

#### Parameters

`registries``:`` ``list[BaseRegistry]`  
List of BaseRegistry objects to deduplicate.

### get_image()

Returns an image by name, or None if not found.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L153-L161)

``` python
get_image(name)
```

#### Parameters

`name``:`` ``str`  
The name of the image to get.

### resolve_parentage()

Sets the parent reference for the Repository and Image child objects.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L140-L146)

``` python
resolve_parentage()
```

Back to top
