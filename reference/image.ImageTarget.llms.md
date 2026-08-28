# image.ImageTarget

# image.ImageTarget

Represents a combination of image variant, image version, and image version OS that make up a target image.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/image_target.py#L221-L835)

``` python
image.ImageTarget()
```

Image targets represent a unique image specified by configuration elements. Image targets are the functional representation of a bakery.yaml configuration and can be used for various operations such as: - Build - Push - Bake - Goss Test

## Attributes

| Name | Description |
|----|----|
| [build_args](#build_args) | Generate build arguments for the image based on its properties. |
| [build_target](#build_target) | Return the target build stage, if configured. |
| [containerfile](#containerfile) | Return the path of the Containerfile for this image target. |
| [image_name](#image_name) | Return the name of the image. |
| [is_channel_latest](#is_channel_latest) | Check whether this build targets the current channel head. |
| [is_latest](#is_latest) | Check if the image version is marked as latest. |
| [is_latest_patch_combination](#is_latest_patch_combination) | Check if the image version is the latest patch for its matrix (minor, …) group. |
| [is_primary_os](#is_primary_os) | Check if the image OS is marked as primary. |
| [is_primary_variant](#is_primary_variant) | Check if the image variant is marked as primary. |
| [labels](#labels) | Generate labels for the image based on its properties. |
| [push_sort_key](#push_sort_key) | Deterministic ordering for push to ordered-display registries (e.g. Docker Hub). |
| [release_channel](#release_channel) | The release channel for this target, defaulting to `release` when unset. |
| [release_channels](#release_channels) | Every release channel whose floating tag this build carries. |
| [resolved_build_secrets](#resolved_build_secrets) | Return the parent Image’s BuildSecrets whose envVar is set in the environment. |
| [tag_patterns](#tag_patterns) | Ensure tag patterns are unique. |
| [tag_suffixes](#tag_suffixes) | Generate tag suffixes from set patterns. |
| [tag_template_values](#tag_template_values) | Return a dictionary of values for templating tags. |
| [tags](#tags) | Generate tags for the image based on tag patterns. |
| [temp_name](#temp_name) | Generate the image name and tag to use for temporary image storage in multiplatform split/merge builds. |
| [temp_registry](#temp_registry) | Get the temporary registry from settings. |
| [uid](#uid) | Generate a unique identifier for the target. |

### build_args

Generate build arguments for the image based on its properties.

`build_args``:`` ``dict[str, str]`

### build_target

Return the target build stage, if configured.

`build_target``:`` ``str | None`

Resolves hierarchically: ImageVersion \> ImageMatrix \> Image. Matrix values are propagated to versions at creation time, so the fallback here is version -\> parent image.

### containerfile

Return the path of the Containerfile for this image target.

`containerfile``:`` ``Path`

### image_name

Return the name of the image.

`image_name``:`` ``str`

### is_channel_latest

Check whether this build targets the current channel head.

`is_channel_latest``:`` ``bool`

Returns False when the build was dispatched with an older version override so that floating {{ Channel }} tags (which should always point at the head) are suppressed. Defaults to True for non-channel sources.

### is_latest

Check if the image version is marked as latest.

`is_latest``:`` ``bool`

### is_latest_patch_combination

Check if the image version is the latest patch for its matrix (minor, …) group.

`is_latest_patch_combination``:`` ``bool`

### is_primary_os

Check if the image OS is marked as primary.

`is_primary_os``:`` ``bool`

### is_primary_variant

Check if the image variant is marked as primary.

`is_primary_variant``:`` ``bool`

### labels

Generate labels for the image based on its properties.

`labels``:`` ``dict[str, str]`

### push_sort_key

Deterministic ordering for push to ordered-display registries (e.g. Docker Hub).

`push_sort_key``:`` ``tuple[str, bool, ParsedVersion, int, str, str, str]`

Tuple semantics, ascending sort: 1. image_name — group all targets of one image together. 2. is_latest — False before True; latest target pushed LAST in its group. 3. version — ParsedVersion (semver §11) or MIN for matrix/unparseable. 4. primary_score — 0..2; (primary OS + primary variant) target pushes LAST within a version, so its simplest tag is most-recent. 5. version.name — stable lex tiebreaker (load-bearing for matrix rows that collapse to MIN under (3)). 6. variant.name — stable tiebreaker. 7. os.name — stable tiebreaker.

### release_channel

The release channel for this target, defaulting to `release` when unset.

`release_channel``:`` ``ReleaseChannelEnum`

### release_channels

Every release channel whose floating tag this build carries.

`release_channels``:`` ``list[ReleaseChannelEnum]`

Normally one, but when multiple dev channels collapse to the same version (e.g. daily and preview both at the current head between branch cut and release, \#632) the single build floats every collapsed channel’s tag.

### resolved_build_secrets

Return the parent Image’s BuildSecrets whose envVar is set in the environment.

`resolved_build_secrets``:`` ``list[BuildSecret]`

Secrets whose envVar is unset are skipped with a warning; the build command itself decides whether a missing secret is fatal (via `required=true` on the Dockerfile mount). Each build path (sequential, bake) formats these into its own option shape.

### tag_patterns

Ensure tag patterns are unique.

`tag_patterns``:`` ``list[TagPattern]`

### tag_suffixes

Generate tag suffixes from set patterns.

`tag_suffixes``:`` ``list[str]`

Channel-bearing patterns render once per collapsed release channel so a single build can float every channel’s tag (#632); all others render once.

### tag_template_values

Return a dictionary of values for templating tags.

`tag_template_values``:`` ``dict[str, str]`

### tags

Generate tags for the image based on tag patterns.

`tags``:`` ``StringableList[Tag]`

### temp_name

Generate the image name and tag to use for temporary image storage in multiplatform split/merge builds.

`temp_name``:`` ``str | None`

### temp_registry

Get the temporary registry from settings.

`temp_registry``:`` ``str | None`

### uid

Generate a unique identifier for the target.

`uid``:`` ``str`

The channel is appended for development versions so a dev build and a release build of the same version never share a UID. Release UIDs stay unsuffixed.

## Methods

| Name | Description |
|----|----|
| [\_\_str\_\_()](#__str__) | Return a string representation of the image target. |
| [build()](#build) | Build the image using the Containerfile and return the built image. |
| [build_metadata_for_platform()](#build_metadata_for_platform) | Returns the most recent build metadata matching `platform`, if any. |
| [cache_name()](#cache_name) | Generate the image name and tag to use for a build cache. |
| [get_merge_sources()](#get_merge_sources) | Get the list of source image references to use for merging. |
| [get_tool_option()](#get_tool_option) | Returns tool options for this image target, falling back from variant to parent image. |
| [load_build_metadata_from_file()](#load_build_metadata_from_file) | Load build metadata from a given file. |
| [new_image_target()](#new_image_target) | Create a new ImageTarget instance from a repository, version, variant, and OS combination. |
| [ref()](#ref) | Returns a reference to the image, preferring a build metadata digest if available. |
| [remove()](#remove) | Remove the image from the local image cache or registry. |

### \_\_str\_\_()

Return a string representation of the image target.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/image_target.py#L276-L284)

``` python
__str__()
```

### build()

Build the image using the Containerfile and return the built image.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/image_target.py#L716-L815)

``` python
build(
    load=True,
    push=False,
    pull=False,
    cache=True,
    platforms=None,
    metadata_file=None,
    log_callback=None
)
```

When `log_callback` is set, streams build output line-by-line into it and returns `None` instead of a `python_on_whales.Image` (`python_on_whales` returns an iterator of lines rather than an `Image` object when streaming).

### build_metadata_for_platform()

Returns the most recent build metadata matching `platform`, if any.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/image_target.py#L556-L567)

``` python
build_metadata_for_platform(platform)
```

Shares `ref()`’s newest-first, platform-filtered selection so callers that need the underlying `BuildMetadata` (e.g. for provenance fields) see the same artifact `ref()` would resolve to.

### cache_name()

Generate the image name and tag to use for a build cache.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/image_target.py#L605-L625)

``` python
cache_name(platform=None)
```

#### Parameters

`platform``:`` ``str | None`` ``=`` ``None`  
Optional platform string (e.g., “linux/amd64”) to include in the cache tag for platform-specific cache differentiation.

### get_merge_sources()

Get the list of source image references to use for merging.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/image_target.py#L817-L835)

``` python
get_merge_sources()
```

Sources collected will be the most recent artifact for each platform represented in the build metadata.

### get_tool_option()

Returns tool options for this image target, falling back from variant to parent image.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/image_target.py#L676-L696)

``` python
get_tool_option(tool)
```

When the target has a variant, this delegates to `ImageVariant.get_tool_option`, which already merges the variant’s options with its parent `Image`’s options. When the target has no variant, this falls back directly to the parent `Image`’s own `get_tool_option` so variant-less images can still configure tool options via `Image.options` in bakery.yaml, instead of that configuration being silently ignored.

#### Parameters

`tool``:`` ``str`  
The name of the tool to get options for.

#### Returns

` ``ToolOptions | None`  
The ToolOptions object for the specified tool, or None if not found.

### load_build_metadata_from_file()

Load build metadata from a given file.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/image_target.py#L705-L714)

``` python
load_build_metadata_from_file(metadata_file)
```

### new_image_target()

Create a new ImageTarget instance from a repository, version, variant, and OS combination.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/image_target.py#L242-L274)

``` python
new_image_target(
    repository,
    image_version,
    image_variant=None,
    image_os=None,
    settings=None
)
```

#### Parameters

`repository``:`` ``Repository`  
The repository containing the image.

`image_version``:`` ``ImageVersion`  
The specific version of the image.

`image_variant``:`` ``ImageVariant | None`` ``=`` ``None`  
The variant of the image, if applicable.

`image_os``:`` ``ImageVersionOS | None`` ``=`` ``None`  
The operating system of the image, if applicable.

`settings``:`` ``ImageTargetSettings | None`` ``=`` ``None`  
Optional settings for the image target.

#### Returns

` ``ImageTarget`  
A new ImageTarget representing the given combination of configurations.

### ref()

Returns a reference to the image, preferring a build metadata digest if available.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/image_target.py#L523-L554)

``` python
ref(platform=f'linux/{SETTINGS.architecture}', *, digest_only=False)
```

#### Parameters

`platform``:`` ``str`` ``=`` ``f``"linux/{SETTINGS.architecture}"`\  
The platform to reference, used for selecting the appropriate build metadata in multi-platform builds. Defaults to the host architecture.

`digest_only``:`` ``bool`` ``=`` ``False`  
Return a tag-free `repo@sha256:DIGEST` reference instead of the default `repo:tag@sha256:DIGEST`. Temp-registry images are pushed by digest and therefore carry no tag in the registry, so consumers that resolve the tag portion rather than ignoring it need the tag-free form.

#### Returns

` ``str`  
A string reference to the image, using the build metadata digest if available, otherwise falling back to the first tag.

### remove()

Remove the image from the local image cache or registry.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/image/image_target.py#L698-L703)

``` python
remove(prune=True, force=False)
```

Back to top
