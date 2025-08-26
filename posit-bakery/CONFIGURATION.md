# Configuration Overview

This document provides an overview of the configuration schema for Bakery, a tool for managing container images. The configuration is defined in a YAML file named `bakery.yaml`. A template for this file can be created using `bakery create project`.

Fields marked as "*Required*" must be provided in the configuration file.

## Bakery Configuration

The top-level Bakery configuration, `bakery.yaml`, is represented in the table below.

| Field                                         | Description                                                |
|-----------------------------------------------|------------------------------------------------------------|
| `repository`<br/>*[Repository](#repository)*  | *(Required)* The project's repository metadata.            |
| `registries`<br/>*[Registry](#registry) list* | The global-level registries to push all project images to. |
| `images`<br/>*[Image](#image) list*           | The list of images managed by the project.                 |

## Metadata Types

### Repository

A Repository stores the metadata of the parent repository of the project. It is primarily used
for labeling images.

| Field                                                         | Description                                                                                           | Default Value                         | Example                                                        |
|---------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|---------------------------------------|----------------------------------------------------------------|
| `url`<br/>*HttpUrl*                                           | *(Required)* The URL of the repository. If a protocol is not specified, `https://` will be prepended. |                                       | "https://github.com/posit-dev/images-shared"                   |
| `vendor`<br/>*string*                                         | The vendor or organization name.                                                                      | `Posit Software, PBC`                 | `Example Organiztion, LLC`                                     |
| `maintainer`<br/>*[NameEmail](#nameemail)* or *string*        | The maintainer of the repository/project.                                                             | `Posit Docker Team <docker@posit.co>` | `Jane Doe <jane.doe@example.com>`                              |
| `authors`<br/>*[NameEmail](#nameemail) list* or *string list* | The credited authors of the repository/project.                                                       |                                       | <pre>- name: Author One<br/>  email: author1@example.com</pre> |

### Registry

A Registry represents a container image registry.

| Field                    | Description                                                     | Example                |
|--------------------------|-----------------------------------------------------------------|------------------------|
| `host`<br/>*string*      | The host of the registry.                                       | `docker.io`, `ghcr.io` |
| `namespace`<br/>*string* | *(Optional)* The namespace or organization within the registry. | `positdev`, `my-org`   |

## Image Specification Types

### Image

An Image represents a container image managed by the project. Each image has one or more versions and optionally can have one or more variants and operating systems.

| Field                                                 | Description                                                                                                                         | Default Value                               | Example                                                                                               |
|-------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------|-------------------------------------------------------------------------------------------------------|
| `name`<br/>*string*                                   | The name of the image. Used as the image name in tags.                                                                              |                                             | `my-image`, `workbench`                                                                               |
| `displayName`<br/>*string*                            | A human-friendly name for the image. Used in labeling.                                                                              | `<name>.replace("-", " ").title()`          | `My Image`                                                                                            |
| `description`<br/>*string*                            | A description of the image. Used in labeling.                                                                                       |                                             | `An example image.`                                                                                   |
| `documentationUrl`<br/>*HttpUrl*                      | A URL to additional image or product documentation. Used in labeling.                                                               |                                             | `https://docs.example.com/my-image`                                                                   |
| `subpath`<br/>*string*                                | The subpath relative from the project root directory where the image's versions and templates are stored.                           | `<name>`                                    | `my_image`, `my/image`                                                                                |
| `extraRegistries`<br/>*[Registry](#registry) list*    | Additional registries to push this image to in addition to the global `registries` in [bakery.yaml](#bakery-configuration).         |                                             |                                                                                                       |
| `overrideRegistries`<br/>*[Registry](#registry) list* | If set, overrides the global `registries` in [bakery.yaml](#bakery-configuration) for this image with the given list of registries. |                                             |                                                                                                       |
| `tagPatterns`<br/>*[TagPattern](#tagpattern) list*    | The list of tag patterns to apply to all versions of this image.                                                                    | [Default Tag Patterns](#default-patterns)   | <pre>- patterns: ["{{ Version }}"]<br/>  only:<br/>    - "primaryOS"<br/>    - "primaryVariant"</pre> |
| `variants`<br/>*[ImageVariant](#imagevariant) list*   | The list of variants for the image. Each variant should have its own `Containerfile`.                                               | [Default Variants](#default-image-variants) |                                                                                                       |
| `versions`<br/>*[ImageVersion](#imageversion) list*   | *(Required)* The list of versions for the image. Each version should have its own directory under the image's `subpath`.            |                                             |                                                                                                       |
| `options`<br/>*[ToolOptions](#tooloptions) list*      | A list of options to pass to a supported tool when performing an action against the image.                                          |                                             |                                                                                                       |

## Other Types

### NameEmail

A NameEmail represents a name and email address pair.

| Field                | Description              | Example              |
|----------------------|--------------------------|----------------------|
| `name`<br/>*string*  | The name of the person.  | Jane Doe             |
| `email`<br/>*string* | The email of the person. | jane.doe@example.com |

### TagPattern

A TagPattern represents a pattern for tagging images. It can include placeholders that are replaced with actual values when generating tags.

| Field                                                   | Description                                                                                                                                           |
|---------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| `patterns`<br/>*string list*                            | *(Required)* The list of Jinja2 patterns for the tag.                                                                                                 |
| `only`<br/>*[TagPatternFilter](#tagpatternfilter) list* | *(Optional)* A list of conditionals to restrict what image targets the tag `patterns` apply to. By default, patterns will apply to all image targets. |

#### Pattern Templating

All [TagPattern](#tagpattern) `patterns` should be valid Jinja2 template strings.

The following variables are available for use in `patterns`:
- `{{ Version }}`: The version of the image.
- `{{ OS }}`: The operating system of the image.
- `{{ Variant }}`: The variant of the image.
- `{{ Name }}`: The name of the image.

In addition to the default Jinja2 filter functions, the following custom filters are also available for use in `patterns`:
- `tagSafe`: Replaces disallowed characters in a tag with a hyphen (`-`). Disallowed characters are any characters other than alphanumeric characters, `.`, `_`, or `-`.
- `stripMetadata`: Removes trailing metadata suffixes in a version that start with `-` or `+`. For example, `1.2.3-rc1` becomes `1.2.3`.
- `condense`: Removes ` `, `.`, and `-` characters.
- `regexReplace <find> <replace>`: Uses `re.sub` to replace occurrences of the `find` regex pattern with the `replace` string.

#### Default Patterns

By default, the following tag patterns will be used for an [Image](#image) if no `tagPatterns` are otherwise specified for the [Image](#image) or [ImageVariant](#imagevariant). These patterns mirror the behavior noted in the [Image Tags](./README.md#image-tags) section of the README.

```yaml
- patterns: ["{{ Version }}-{{ OS }}-{{ Variant }}", "{{ Version | stripMetadata }}-{{ OS }}-{{ Variant }}"]
  only:
    - "all"
- patterns: ["{{ Version }}-{{ Variant }}", "{{ Version | stripMetadata }}-{{ Variant }}"]
  only:
    - "primaryOS"
- patterns: ["{{ Version }}-{{ OS }}", "{{ Version | stripMetadata }}-{{ OS }}"]
  only:
    - "primaryVariant"
- patterns: ["{{ Version }}", "{{ Version | stripMetadata }}"]
  only:
    - "primaryOS"
    - "primaryVariant"
- patterns: ["{{ OS }}-{{ Variant }}"]
  only:
    - "latest"
- patterns: ["{{ OS }}"]
  only:
    - "latest"
    - "primaryVariant"
- patterns: ["{{ Variant }}"]
  only:
    - "latest"
    - "primaryOS"
- patterns: ["latest"]
  only:
    - "latest"
    - "primaryOS"
    - "primaryVariant"
```

#### TagPatternFilter

The following filters can be used in the `only` field of a TagPattern to restrict which image targets the tag patterns apply to:

- `all`: *(Default)* Applies to all image targets.
- `latest`: Applies only to the `latest` version of the image.
- `primaryOS`: Applies only to the `primary` operating system of the image.
- `primaryVariant`: Applies only to the `primary` variant of the image.

### ToolOptions

A ToolOption represents a set of configurable options for a supported tool. Each instance of a ToolOption applies to a specific tool and must specify a valid `tool` name.

#### GossOptions

A GossOption represents options for `dgoss` tests against an image target.

| Field                              | Description                                                                                                                                                   | Default Value                                                                                                      | Example          |
|------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|------------------|
| `tool`<br/>*"goss" literal string* | *(Required)* The name of the tool.                                                                                                                            |                                                                                                                    | `goss`           |
| `runtimeOptions`<br/>*string*      | Additional runtime options to pass to the `dgoss` container instantiation when running tests.                                                                 |                                                                                                                    | `--privileged`   |
| `command`<br/>*string*             |                                                                                                                                                               | The command to run within the `dgoss` container. This can be used to start a service in the container for testing. | `sleep infinity` | `start-server` |
| `wait`<br/>*int*                   | The number of seconds to wait after container startup before running tests. Useful if there is a service that needs to complete its startup prior to testing. | `0`                                                                                                                | `30`             |
