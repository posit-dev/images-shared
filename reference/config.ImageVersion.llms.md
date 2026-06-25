# config.ImageVersion

# config.ImageVersion

Model representing a version of an image.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/version.py#L30-L559)

``` python
config.ImageVersion()
```

## Attributes

| Name | Description |
|----|----|
| [all_registries](#all_registries) | Returns the merged registries for this image version. |
| [parsed_version](#parsed_version) | Return the parsed semver/calver representation of `self.name`. |
| [path](#path) | Returns the path to the image version directory. |
| [supported_platforms](#supported_platforms) | Returns a list of supported target platforms for this image version. |

### all_registries

Returns the merged registries for this image version.

`all_registries``:`` ``list[Registry | BaseRegistry]`

### parsed_version

Return the parsed semver/calver representation of `self.name`.

`parsed_version``:`` ``ParsedVersion | None`

Returns `None` for matrix versions (without warning) and for unparseable names (with a single `log.warning` from `ParsedVersion.parse`).

### path

Returns the path to the image version directory.

`path``:`` ``Path | None`

#### Raises

` ``ValueError`  
If the parent image does not have a valid path.

### supported_platforms

Returns a list of supported target platforms for this image version.

`supported_platforms``:`` ``list[TargetPlatform]`

## Methods

| Name | Description |
|----|----|
| [check_duplicate_dependencies()](#check_duplicate_dependencies) | Ensures that the dependencies list is unique and errors on duplicates. |
| [check_os_not_empty()](#check_os_not_empty) | Ensures that the os list is not empty. |
| [deduplicate_os()](#deduplicate_os) | Ensures that the os list is unique and warns on duplicates. |
| [deduplicate_registries()](#deduplicate_registries) | Ensures that the registries list is unique and warns on duplicates. |
| [extra_registries_or_override_registries()](#extra_registries_or_override_registries) | Ensures that only one of extraRegistries or overrideRegistries is defined. |
| [generate_template_values()](#generate_template_values) | Generates the template values for rendering. |
| [make_single_os_primary()](#make_single_os_primary) | Ensures that at most one OS is marked as primary. |
| [matches_dev_filter()](#matches_dev_filter) | Check whether this version should be included given dev version filters. |
| [max_one_primary_os()](#max_one_primary_os) | Ensures that at most one OS is marked as primary. |
| [render_files()](#render_files) | Render a new image version from the template. |
| [resolve_parentage()](#resolve_parentage) | Sets the parent for all OSes in this image version. |

### check_duplicate_dependencies()

Ensures that the dependencies list is unique and errors on duplicates.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/version.py#L258-L282)

``` python
check_duplicate_dependencies(dependencies, info)
```

#### Parameters

`dependencies``:`` ``list[DependencyVersionsField]`  
List of dependencies to deduplicate.

`info``:`` ``ValidationInfo`  
ValidationInfo containing the data being validated.

#### Returns

` ``list[DependencyVersionsField]`  
A list of unique dependencies.

#### Raises

` ``ValueError`  
If duplicate dependencies are found.

### check_os_not_empty()

Ensures that the os list is not empty.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/version.py#L177-L193)

``` python
check_os_not_empty(os, info)
```

#### Parameters

`os``:`` ``list[ImageVersionOS]`  
List of ImageVersionOS objects to check.

`info``:`` ``ValidationInfo`  
ValidationInfo containing the data being validated.

#### Returns

` ``list[ImageVersionOS]`  
The unmodified list of ImageVersionOS objects.

### deduplicate_os()

Ensures that the os list is unique and warns on duplicates.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/version.py#L195-L210)

``` python
deduplicate_os(os, info)
```

#### Parameters

`os``:`` ``list[ImageVersionOS]`  
List of ImageVersionOS objects to deduplicate.

`info``:`` ``ValidationInfo`  
ValidationInfo containing the data being validated.

#### Returns

` ``list[ImageVersionOS]`  
A list of unique ImageVersionOS objects.

### deduplicate_registries()

Ensures that the registries list is unique and warns on duplicates.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/version.py#L156-L175)

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

### extra_registries_or_override_registries()

Ensures that only one of extraRegistries or overrideRegistries is defined.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/version.py#L284-L294)

``` python
extra_registries_or_override_registries()
```

#### Raises

` ``ValueError`  
If both extraRegistries and overrideRegistries are defined.

### generate_template_values()

Generates the template values for rendering.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/version.py#L361-L403)

``` python
generate_template_values(variant=None, version_os=None)
```

#### Parameters

`variant``:`` ``Union[ImageVariant, None]`` ``=`` ``None`  
The ImageVariant object.

`version_os``:`` ``Union[ImageVersionOS, None]`` ``=`` ``None`  
The ImageVersionOS object, if applicable.

#### Returns

` ``dict[str, Any]`  
A dictionary of values to use for rendering version templates.

### make_single_os_primary()

Ensures that at most one OS is marked as primary.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/version.py#L212-L231)

``` python
make_single_os_primary(os, info)
```

#### Parameters

`os``:`` ``list[ImageVersionOS]`  
List of ImageVersionOS objects to check.

`info``:`` ``ValidationInfo`  
ValidationInfo containing the data being validated.

#### Returns

` ``list[ImageVersionOS]`  
The list of ImageVersionOS objects with at most one primary OS.

### matches_dev_filter()

Check whether this version should be included given dev version filters.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/version.py#L134-L154)

``` python
matches_dev_filter(dev_versions, dev_channel=None)
```

#### Parameters

`dev_versions``:`` ``DevVersionInclusionEnum`  
Whether dev versions are included, excluded, or the only versions.

`dev_channel``:`` ``ReleaseChannelEnum | None`` ``=`` ``None`  
If set, only include dev versions from this release channel.

#### Returns

` ``tuple[bool, str | None]`  
A tuple of (included, reason). If excluded, reason explains why.

### max_one_primary_os()

Ensures that at most one OS is marked as primary.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/version.py#L233-L256)

``` python
max_one_primary_os(os, info)
```

#### Parameters

`os``:`` ``list[ImageVersionOS]`  
List of ImageVersionOS objects to check.

`info``:`` ``ValidationInfo`  
ValidationInfo containing the data being validated.

#### Returns

` ``list[ImageVersionOS]`  
The list of ImageVersionOS objects with at most one primary OS.

#### Raises

` ``ValueError`  
If more than one OS is marked as primary.

### render_files()

Render a new image version from the template.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/version.py#L405-L559)

``` python
render_files(variants=None, regex_filters=None)
```

#### Parameters

`variants``:`` ``list[ImageVariant] | None`` ``=`` ``None`  
Optional list of ImageVariant objects to render Containerfiles for each variant.

`regex_filters``:`` ``list[str] | None`` ``=`` ``None`  
Optional list of regex patterns to filter which templates to render.

#### Raises

` ``BakeryFileError`  
If the template path does not exist.

` ``BakeryRenderError`  
If a template fails to render.

` ``BakeryRenderErrorGroup`  
If multiple templates fail to render.

### resolve_parentage()

Sets the parent for all OSes in this image version.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/image/version.py#L296-L301)

``` python
resolve_parentage()
```

Back to top
