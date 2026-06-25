# config.Image

# config.Image

Model representing an image in the bakery configuration.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L26-L614)

``` python
config.Image()
```

## Attributes

| Name | Description |
|----|----|
| [all_registries](#all_registries) | Returns the merged registries for this image. |
| [path](#path) | Returns the path to the image directory. |
| [template_path](#template_path) | Returns the path to the image template directory. |

### all_registries

Returns the merged registries for this image.

`all_registries``:`` ``list[Registry | BaseRegistry]`

### path

Returns the path to the image directory.

`path``:`` ``Path | None`

### template_path

Returns the path to the image template directory.

`template_path``:`` ``Path`

## Methods

| Name | Description |
|----|----|
| [check_dependency_constraints_with_matrix()](#check_dependency_constraints_with_matrix) | Checks if dependencyConstraints and matrix are both defined. |
| [check_duplicate_dependency_constraints()](#check_duplicate_dependency_constraints) | Ensures that there are no duplicate dependencies in the image. |
| [check_not_empty()](#check_not_empty) | Ensures one version or matrix is defined. |
| [check_variant_duplicates()](#check_variant_duplicates) | Ensures that there are no duplicate variant names in the image. |
| [check_version_duplicates()](#check_version_duplicates) | Ensures that there are no duplicate version names in the image. |
| [create_matrix()](#create_matrix) | Creates a new image version and adds it to the image. |
| [create_version()](#create_version) | Creates a new image version and adds it to the image. |
| [deduplicate_registries()](#deduplicate_registries) | Ensures that the registries list is unique and warns on duplicates. |
| [default_https_url_scheme()](#default_https_url_scheme) | Prepend ‘https://’ to the URL if it does not already start with it. |
| [extra_registries_or_override_registries()](#extra_registries_or_override_registries) | Ensures that only one of extraRegistries or overrideRegistries is defined. |
| [get_tool_option()](#get_tool_option) | Returns the Goss options for this image variant. |
| [get_variant()](#get_variant) | Returns an image variant by name, or None if not found. |
| [get_version()](#get_version) | Returns an image version by name, or None if not found. |
| [get_version_by_subpath()](#get_version_by_subpath) | Returns an image version by subpath, or None if not found. |
| [load_dev_versions()](#load_dev_versions) | Load the development versions for this image. |
| [patch_version()](#patch_version) | Patches an existing image version with a new version name. |
| [remove_ephemeral_version_files()](#remove_ephemeral_version_files) | Remove the files for all ephemeral image versions. |
| [render_ephemeral_version_files()](#render_ephemeral_version_files) | Create the files for all ephemeral image versions. |
| [resolve_dependency_versions()](#resolve_dependency_versions) | Resolves the dependency versions for this image. |
| [resolve_parentage()](#resolve_parentage) | Sets the parent for all variants and versions in this image. |
| [serialize_documentation_url()](#serialize_documentation_url) | Serializes the documentation URL to a string. |

### check_dependency_constraints_with_matrix()

Checks if dependencyConstraints and matrix are both defined.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L270-L282)

``` python
check_dependency_constraints_with_matrix()
```

Warns if dependencyConstraints will be ineffectual as they must be defined at matrix-level.

### check_duplicate_dependency_constraints()

Ensures that there are no duplicate dependencies in the image.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L169-L194)

``` python
check_duplicate_dependency_constraints(dependency_constraints, info)
```

#### Parameters

`dependency_constraints``:`` ``list[DependencyConstraintField]`  
List of DependencyConstraintField objects to check for duplicates.

`info``:`` ``ValidationInfo`  
ValidationInfo containing the data being validated.

#### Returns

` ``list[DependencyConstraintField]`  
The unmodified list of DependencyConstraintField objects if no duplicates are found.

#### Raises

` ``ValueError`  
If duplicate dependencies are found.

### check_not_empty()

Ensures one version or matrix is defined.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L257-L268)

``` python
check_not_empty()
```

#### Returns

` ``Self`  
The unmodified Image object.

### check_variant_duplicates()

Ensures that there are no duplicate variant names in the image.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L220-L242)

``` python
check_variant_duplicates(variants, info)
```

#### Parameters

`variants``:`` ``list[ImageVariant]`  
List of ImageVariant objects to check for duplicates.

`info``:`` ``ValidationInfo`  
ValidationInfo containing the data being validated.

#### Returns

` ``list[ImageVariant]`  
The unmodified list of ImageVariant objects if no duplicates are found.

#### Raises

` ``ValueError`  
If duplicate variant names are found.

### check_version_duplicates()

Ensures that there are no duplicate version names in the image.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L196-L218)

``` python
check_version_duplicates(versions, info)
```

#### Parameters

`versions``:`` ``list[ImageVersion]`  
List of ImageVersion objects to check for duplicates.

`info``:`` ``ValidationInfo`  
ValidationInfo containing the data being validated.

#### Returns

` ``list[ImageVersion]`  
The unmodified list of ImageVersion objects if no duplicates are found.

#### Raises

` ``ValueError`  
If duplicate version names are found.

### create_matrix()

Creates a new image version and adds it to the image.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L461-L523)

``` python
create_matrix(
    name_pattern=None,
    subpath=None,
    dependency_constraints=None,
    dependencies=None,
    values=None,
    update_if_exists=False
)
```

#### Parameters

`name_pattern``:`` ``str | None`` ``=`` ``None`  
The name pattern for the new image version. If None, defaults to the version name with spaces replaced by hyphens and lowercase.

`subpath``:`` ``str | None`` ``=`` ``None`  
Optional subpath for the new version. If None, defaults to the version name with spaces replaced by hyphens and lowercase.

`dependency_constraints``:`` ``list[DependencyConstraint] | None`` ``=`` ``None`  
Optional list of DependencyConstraint objects to use for resolving dependencies for the new version.

`dependencies``:`` ``list[DependencyVersions] | None`` ``=`` ``None`  
Optional list of DependencyVersions objects to use for the new version.

`values``:`` ``dict[str, str] | None`` ``=`` ``None`  
Optional dictionary of additional key-value pairs to include in the template values.

`update_if_exists``:`` ``bool`` ``=`` ``False`  
If True, updates the existing version if it already exists, otherwise raises an error if the version exists.

#### Returns

` ``ImageMatrix`  
The created or updated ImageVersion object.

### create_version()

Creates a new image version and adds it to the image.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L380-L459)

``` python
create_version(
    version_name,
    subpath=None,
    values=None,
    latest=True,
    update_if_exists=False
)
```

#### Parameters

`version_name``:`` ``str`  
The name of the new image version.

`subpath``:`` ``str | None`` ``=`` ``None`  
Optional subpath for the new version. If None, defaults to the version name with spaces replaced by hyphens and lowercase.

`values``:`` ``dict[str, str] | None`` ``=`` ``None`  
Optional dictionary of additional key-value pairs to include in the template values.

`latest``:`` ``bool`` ``=`` ``True`  
If True, sets this version as the latest version of the image. Unsets latest on all other image versions.

`update_if_exists``:`` ``bool`` ``=`` ``False`  
If True, updates the existing version if it already exists, otherwise raises an error if the version exists.

#### Returns

` ``ImageVersion`  
The created or updated ImageVersion object.

### deduplicate_registries()

Ensures that the registries list is unique and warns on duplicates.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L137-L155)

``` python
deduplicate_registries(registries, info)
```

#### Parameters

`registries``:`` ``list[Registry | BaseRegistry]`  
List of registries to deduplicate.

`info``:`` ``ValidationInfo`  
ValidationInfo containing the data being validated.

#### Returns

` ``list[Registry | BaseRegistry]`  
A list of unique registries.

### default_https_url_scheme()

Prepend ‘https://’ to the URL if it does not already start with it.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L125-L135)

``` python
default_https_url_scheme(value)
```

#### Parameters

`value``:`` ``Any`  
The URL to validate and possibly modify.

### extra_registries_or_override_registries()

Ensures that only one of extraRegistries or overrideRegistries is defined.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L157-L167)

``` python
extra_registries_or_override_registries()
```

#### Raises

` ``ValueError`  
If both extraRegistries and overrideRegistries are defined.

### get_tool_option()

Returns the Goss options for this image variant.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L328-L339)

``` python
get_tool_option(tool)
```

#### Parameters

`tool``:`` ``str`  
The name of the tool to get options for.

#### Returns

` ``ToolOptions | None`  
The ToolOptions object for the specified tool, or None if not found.

### get_variant()

Returns an image variant by name, or None if not found.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L341-L352)

``` python
get_variant(name)
```

#### Parameters

`name``:`` ``str`  
The name property of the image variant to find.

#### Returns

` ``ImageVariant | None`  
The ImageVariant object if found, otherwise None.

### get_version()

Returns an image version by name, or None if not found.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L354-L365)

``` python
get_version(name)
```

#### Parameters

`name``:`` ``str`  
The name property of the image version to find.

#### Returns

` ``ImageVersion | None`  
The ImageVersion object if found, otherwise None.

### get_version_by_subpath()

Returns an image version by subpath, or None if not found.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L367-L378)

``` python
get_version_by_subpath(subpath)
```

#### Parameters

`subpath``:`` ``str`  
The subpath to match against.

#### Returns

` ``ImageVersion | None`  
The ImageVersion object if found, otherwise None.

### load_dev_versions()

Load the development versions for this image.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L587-L600)

``` python
load_dev_versions()
```

### patch_version()

Patches an existing image version with a new version name.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L525-L585)

``` python
patch_version(old_version_name, new_version_name, values=None, clean=True)
```

#### Parameters

`old_version_name``:`` ``str`  
The existing version name to be patched.

`new_version_name``:`` ``str`  
The new version name to replace the old version with.

`values``:`` ``dict[str, str]`` ``=`` ``None`  
Optional dictionary of additional key-value pairs to include or update in the template values.

`clean``:`` ``bool`` ``=`` ``True`  
If True, removes all existing version files before rendering the new version files

#### Returns

` ``ImageVersion`  
The patched ImageVersion object.

### remove_ephemeral_version_files()

Remove the files for all ephemeral image versions.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L609-L614)

``` python
remove_ephemeral_version_files()
```

### render_ephemeral_version_files()

Create the files for all ephemeral image versions.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L602-L607)

``` python
render_ephemeral_version_files()
```

### resolve_dependency_versions()

Resolves the dependency versions for this image.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L321-L326)

``` python
resolve_dependency_versions()
```

#### Returns

` ``list[DependencyVersions]`  
A list of DependencyVersions objects with resolved versions.

### resolve_parentage()

Sets the parent for all variants and versions in this image.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L244-L255)

``` python
resolve_parentage()
```

### serialize_documentation_url()

Serializes the documentation URL to a string.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/image.py#L284-L289)

``` python
serialize_documentation_url(value)
```

Back to top
