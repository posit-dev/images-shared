# config.BakeryConfig

# config.BakeryConfig

Manager for the bakery.yaml configuration file and operations against the configuration.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L484-L1305)

``` python
config.BakeryConfig()
```

## Attributes

`yaml`  
The YAML parser used to read and write the bakery.yaml file.

`config_file`  
Path to the bakery.yaml configuration file.

`base_path`  
The base path where the bakery.yaml file is located.

`model`  
The BakeryConfigDocument model representation of the bakery.yaml file.

`targets`  
List of ImageTarget objects representing the image build targets defined in the config.

## Methods

| Name | Description |
|----|----|
| [\_\_init\_\_()](#__init__) | Initializes the BakeryConfig with the given config file path. |
| [bake_plan_targets()](#bake_plan_targets) | Generates a bake plan JSON string for the image targets defined in the config. |
| [build_targets()](#build_targets) | Build image targets using the specified strategy. |
| [clean_caches()](#clean_caches) | Cleans up dangling caches in the specified registry for all generated image targets. |
| [clean_temporary()](#clean_temporary) | Cleans up temporary images in the specified registry for all generated image targets. |
| [create_image()](#create_image) | Creates a new image. |
| [create_matrix()](#create_matrix) | Creates a matrix definition for an image. |
| [create_version()](#create_version) | Creates a new version for an image. |
| [from_context()](#from_context) | Creates a BakeryConfig instance from a given context path. |
| [generate_image_targets()](#generate_image_targets) | Generates image targets from the images defined in the config. |
| [get_image_target_by_uid()](#get_image_target_by_uid) | Returns an image target by its UID. |
| [load_build_metadata_from_file()](#load_build_metadata_from_file) | Loads build metadata from a given metadata file. |
| [new()](#new) | Creates a new bakery.yaml file in the given base path. |
| [patch_version()](#patch_version) | Patches an existing image version with a new version and regenerates templates. |
| [remove_image()](#remove_image) | Removes an image from the config and deletes its directory. |
| [remove_version()](#remove_version) | Removes an existing version from an image in the config. |
| [rerender_files()](#rerender_files) | Regenerates version files from templates matching the given filters. |
| [write()](#write) | Write the bakery config to the config file. |

### \_\_init\_\_()

Initializes the BakeryConfig with the given config file path.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L494-L546)

``` python
__init__(config_file, settings=None)
```

#### Parameters

`config_file``:`` ``str | Path | os.PathLike`  
Path to the target bakery.yaml configuration file.

`settings``:`` ``BakerySettings | None`` ``=`` ``None`  
Optional BakeryConfigFilter to apply when generating image targets.

#### Raises

` ``FileNotFoundError`  
If the config file does not exist.

### bake_plan_targets()

Generates a bake plan JSON string for the image targets defined in the config.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L1145-L1152)

``` python
bake_plan_targets(push=False)
```

#### Parameters

`push``:`` ``bool`` ``=`` ``False`  
When True, include cache-to exports in the bake plan so that cache layers are written to the registry alongside the built images.

### build_targets()

Build image targets using the specified strategy.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L1154-L1251)

``` python
build_targets(
    load=True,
    push=False,
    pull=False,
    cache=True,
    platforms=None,
    strategy=ImageBuildStrategy.BAKE,
    metadata_file=None,
    fail_fast=False,
    retry=0,
    jobs=None
)
```

#### Parameters

`load``:`` ``bool`` ``=`` ``True`  
If True, load the built images into the local Docker daemon.

`push``:`` ``bool`` ``=`` ``False`  
If True, push the built images to the configured registries.

`pull``:`` ``bool`` ``=`` ``False`  
If True, always pull the latest version of base images.

`cache``:`` ``bool`` ``=`` ``True`  
If True, use the build cache when building images.

`platforms``:`` ``list[str] | None`` ``=`` ``None`  
Optional list of platforms to build for. If None, builds for the configuration specified platform.

`strategy``:`` ``ImageBuildStrategy`` ``=`` ``ImageBuildStrategy.BAKE`    
The strategy to use when building images.

`metadata_file``:`` ``Path | None`` ``=`` ``None`  
Optional path to a metadata file to write build metadata to.

`fail_fast``:`` ``bool`` ``=`` ``False`  
If True, stop building targets on the first failure. Only affects targets whose build has not yet started; already-running builds finish.

`retry``:`` ``int`` ``=`` ``0`  
Number of times to retry a failed build (default 0, no retries).

`jobs``:`` ``int | None`` ``=`` ``None`  
Maximum number of targets to build concurrently for `--strategy build` (ignored for `--strategy bake`, which manages its own parallelism). Falls back to `SETTINGS.max_concurrency` when not given.

### clean_caches()

Cleans up dangling caches in the specified registry for all generated image targets.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L1253-L1278)

``` python
clean_caches(remove_untagged=True, remove_older_than=None, dry_run=False)
```

#### Parameters

`remove_untagged``:`` ``bool`` ``=`` ``True`  
If True, remove untagged caches.

`remove_older_than``:`` ``timedelta | None`` ``=`` ``None`  
Optional timedelta to remove caches older than the specified duration.

`dry_run``:`` ``bool`` ``=`` ``False`  
If True, print what would be deleted without actually deleting anything.

### clean_temporary()

Cleans up temporary images in the specified registry for all generated image targets.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L1280-L1305)

``` python
clean_temporary(remove_untagged=True, remove_older_than=None, dry_run=False)
```

#### Parameters

`remove_untagged``:`` ``bool`` ``=`` ``True`  
If True, remove untagged images.

`remove_older_than``:`` ``timedelta | None`` ``=`` ``None`  
Optional timedelta to remove images older than the specified duration.

`dry_run``:`` ``bool`` ``=`` ``False`  
If True, print what would be deleted without actually deleting anything.

### create_image()

Creates a new image.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L618-L651)

``` python
create_image(
    image_name,
    base_image=None,
    subpath=None,
    display_name=None,
    description=None,
    documentation_url=None
)
```

Creates a new image directory, adds the image to the config, and writes the image back to bakery.yaml.

#### Parameters

`image_name``:`` ``str`  
The name of the image to create.

`base_image``:`` ``str | None`` ``=`` ``None`  
Optional base image to use in the Containerfile template. This is used in the `FROM` directive.

`subpath``:`` ``str | None`` ``=`` ``None`  
Optional subpath for the image. If not provided, the image name will be used as the subpath.

`display_name``:`` ``str | None`` ``=`` ``None`  
Optional display name for the image. If not provided, the image name will be used.

`description``:`` ``str | None`` ``=`` ``None`  
Optional description for the image. Used in labels.

`documentation_url``:`` ``str | None`` ``=`` ``None`  
Optional URL for the image documentation. Used in labels.

### create_matrix()

Creates a matrix definition for an image.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L791-L868)

``` python
create_matrix(
    image_name,
    name_pattern=None,
    subpath=None,
    dependency_constraints=None,
    dependencies=None,
    values=None,
    force=False
)
```

Creates a new matrix directory from image templates, add the matrix definition to the config, and writes the matrix back to bakery.yaml.

#### Parameters

`image_name``:`` ``str`  
The name of the image to create the matrix for.

`name_pattern``:`` ``str | None`` ``=`` ``None`  
Optional name pattern for the matrix versions. If not provided, the default pattern will be used.

`subpath``:`` ``str | None`` ``=`` ``None`  
Optional subpath for the matrix. If not provided, the matrix name will be used as the subpath.

`dependency_constraints``:`` ``list[DependencyConstraint] | None`` ``=`` ``None`  
Optional list of DependencyConstraint objects to define constraints for the matrix.

`dependencies``:`` ``list[DependencyVersions] | None`` ``=`` ``None`  
Optional list of DependencyVersions objects to define dependencies for the matrix.

`values``:`` ``dict[str, str] | None`` ``=`` ``None`  
Optional dictionary of values to use in the matrix. This can be used to provide additional context or configuration for the matrix. Often used to specify unmanaged dependency versions.

`force``:`` ``bool`` ``=`` ``False`  
If True, will overwrite an existing matrix.

### create_version()

Creates a new version for an image.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L679-L755)

``` python
create_version(
    image_name, version, subpath=None, values=None, latest=True, force=False
)
```

Creates a new version directory from image templates, add the version to the image config, and writes the version back to bakery.yaml.

#### Parameters

`image_name``:`` ``str`  
The name of the image to create the version for.

`version``:`` ``str`  
The version name to create.

`subpath``:`` ``str | None`` ``=`` ``None`  
Optional subpath for the version. If not provided, the version name will be used as the subpath.

`values``:`` ``dict[str, str] | None`` ``=`` ``None`  
Optional dictionary of values to use in the version. This can be used to provide additional context or configuration for the version. Often used to specify versions of R, Python, or Quarto.

`latest``:`` ``bool`` ``=`` ``True`  
Whether this version should be marked as the latest version.

`force``:`` ``bool`` ``=`` ``False`  
If True, will overwrite an existing version with the same name.

### from_context()

Creates a BakeryConfig instance from a given context path.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L548-L572)

``` python
from_context(context, settings=None)
```

#### Parameters

`context``:`` ``str | Path | os.PathLike`  
The path to the bakery.yaml file or its parent directory.

`settings``:`` ``BakerySettings | None`` ``=`` ``None`  
Optional BakerySettings to apply when generating image targets.

#### Returns

` ``BakeryConfig`  
A BakeryConfig instance.

#### Raises

` ``FileNotFoundError`  
If no bakery.yaml or bakery.yml file is found in the context path.

### generate_image_targets()

Generates image targets from the images defined in the config.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L956-L1104)

``` python
generate_image_targets(settings=BakerySettings())
```

#### Parameters

`settings``:`` ``BakerySettings`` ``=`` ``BakerySettings()`    
Optional settings to apply when generating image targets. If None, all images will be included.

### get_image_target_by_uid()

Returns an image target by its UID.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L1106-L1114)

``` python
get_image_target_by_uid(uid)
```

#### Parameters

`uid``:`` ``str`  
The UID of the image target to find.

#### Returns

` ``ImageTarget | None`  
The ImageTarget with the given UID, or None if not found.

### load_build_metadata_from_file()

Loads build metadata from a given metadata file.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L1128-L1143)

``` python
load_build_metadata_from_file(metadata_file)
```

#### Parameters

`metadata_file``:`` ``Path`  
Path to the metadata file to load.

#### Returns

` ``list[str]`  
A list of targets loaded.

### new()

Creates a new bakery.yaml file in the given base path.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L574-L585)

``` python
new(base_path)
```

#### Attributes

`base_path`  
The path where the new bakery.yaml file will be created.

### patch_version()

Patches an existing image version with a new version and regenerates templates.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L757-L789)

``` python
patch_version(image_name, old_version, new_version, values=None, clean=True)
```

### remove_image()

Removes an image from the config and deletes its directory.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L653-L677)

``` python
remove_image(image_name)
```

#### Parameters

`image_name``:`` ``str`  
The name of the image to remove.

### remove_version()

Removes an existing version from an image in the config.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L921-L954)

``` python
remove_version(image_name, version_name)
```

#### Parameters

`image_name``:`` ``str`  
The name of the image to which the version belongs.

`version_name``:`` ``str`  
The name of the version to remove.

### rerender_files()

Regenerates version files from templates matching the given filters.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L870-L919)

``` python
rerender_files(_filter=None, regex_filters=None)
```

#### Parameters

`_filter``:`` ``BakeryConfigFilter | None`` ``=`` ``None`  
A BakeryConfigFilter to apply when regenerating version files.

`regex_filters``:`` ``list[str] | None`` ``=`` ``None`  
A list of regex patterns to filter which templates to render.

#### Raises

` ``BakeryFileError`  
If any errors occur while regenerating version files.

### write()

Write the bakery config to the config file.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/config.py#L587-L591)

``` python
write()
```

Back to top
