# Configuration Overview

This document provides an overview of the configuration schema for Bakery, a tool for managing container images. The configuration is defined in a YAML file named `bakery.yaml`. A template for this file can be created using `bakery create project`.

Fields marked as "*Required*" must be provided in the configuration file.

## Bakery Configuration

The top-level Bakery configuration, `bakery.yaml`, is represented in the table below.

| Field                                          | Description                                                |
|------------------------------------------------|------------------------------------------------------------|
| `repository`<br/>*[Repository](#repository)*   | *(Required)* The project's repository metadata.            |
| `registries`<br/>*[Registry](#registry) array* | The global-level registries to push all project images to. |
| `images`<br/>*[Image](#image) array*           | The list of images managed by the project.                 |

### Example Configuration

```yaml
repository:
  url: https://github.com/posit-dev/images-shared
  vendor: Posit Software, PBC
  maintainer: Posit Docker Team <docker@posit.co>
  authors:
    - name: Ben Schwedler
      email: ben@posit.co
    - name: Ian Pittwood
      email: ian.pittwood@posit.co

registries:
  - host: ghcr.io
    namespace: posit-dev
  - host: docker.io
    namespace: posit

images:
  - name: workbench
    displayName: Posit Workbench
    description: A containerized image of Posit Workbench, a remote development environment for data scientists.
    documentationUrl: https://docs.posit.co/ide/
    variants:
      - name: Standard
        extension: std
        tagDisplayName: std
        primary: true
        options:
          - tool: goss
            wait: 15
            command: "/usr/bin/supervisord -c /etc/supervisor/supervisord.conf"
      - name: Minimal
        extension: min
        tagDisplayName: min
    versions:
      - name: "2025.05.1+513.pro3"
        subpath: "2025.05"
        latest: true
        os:
        - name: Ubuntu 24.04
          primary: true
          extension: ubuntu2404
          tagDisplayName: ubuntu24.04
        - name: Ubuntu 22.04
          extension: ubuntu2204
          tagDisplayName: ubuntu22.04
      - name: "2024.12.1+563.pro2"
        subpath: "2024.12"
        os:
        - name: Ubuntu 22.04
          primary: true
          extension: ubuntu2204
          tagDisplayName: ubuntu22.04
  - name: workbench-session
    subpath: session
    displayName: Posit Workbench Session
    description: A minimal containerized image for running sessions for Posit Workbench in distributed environments.
    documentationUrl: https://docs.posit.co/ide/server-pro/admin/job_launcher/kubernetes_plugin.html
    versions:
      - name: "2025.05.1+513.pro3"
        subpath: "2025.05"
        latest: true
        os:
        - name: Ubuntu 24.04
          primary: true
          extension: ubuntu2404
          tagDisplayName: ubuntu24.04
        - name: Ubuntu 22.04
          extension: ubuntu2204
          tagDisplayName: ubuntu22.04
      - name: "2024.12.1+563.pro2"
        subpath: "2024.12"
        os:
        - name: Ubuntu 22.04
          primary: true
          extension: ubuntu2204
          tagDisplayName: ubuntu22.04
```

## Metadata Types

### Repository

A Repository stores the metadata of the parent source code repository of the project. It is primarily used
for labeling images.

| Field                                                           | Description                                                                                                             | Default Value                         | Example                                                                                           |
|-----------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------|---------------------------------------|---------------------------------------------------------------------------------------------------|
| `url`<br/>*HttpUrl*                                             | *(Required)* The URL of the image source code repository. If a protocol is not specified, `https://` will be prepended. |                                       | "https://github.com/posit-dev/images-shared"                                                      |
| `vendor`<br/>*string*                                           | The vendor or organization name.                                                                                        | `Posit Software, PBC`                 | `Example Organization, LLC`                                                                       |
| `maintainer`<br/>*[NameEmail](#nameemail)* or *string*          | The maintainer of the repository/project.                                                                               | `Posit Docker Team <docker@posit.co>` | `Jane Doe <jane.doe@example.com>`                                                                 |
| `authors`<br/>*[NameEmail](#nameemail) array* or *string array* | The credited authors of the repository/project.                                                                         | `[]`                                  | <pre>- name: Author One<br/>  email: author1@example.com</pre> |

### Registry

A Registry represents a container image registry.

| Field                    | Description                                                     | Example                |
|--------------------------|-----------------------------------------------------------------|------------------------|
| `host`<br/>*string*      | The host of the registry.                                       | `docker.io`, `ghcr.io` |
| `namespace`<br/>*string* | *(Optional)* The namespace or organization within the registry. | `posit-dev`, `my-org`  |

## Image Specification Types

### Image

An Image represents a container image managed by the project. Each image has one or more versions and optionally can have one or more variants and operating systems. New images can be created using the `bakery create image` command.

| Field                                                  | Description                                                                                                                         | Default Value                               | Example                                                                                                                                  |
|--------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|
| `name`<br/>*string*                                    | The name of the image. Used as the image name in tags.                                                                              |                                             | `my-image`, `workbench`                                                                                                                  |
| `displayName`<br/>*string*                             | A human-friendly name for the image. Used in labeling.                                                                              | `<name>.replace("-", " ").title()`          | `My Image`                                                                                                                               |
| `description`<br/>*string*                             | A description of the image. Used in labeling.                                                                                       |                                             | `An example image.`                                                                                                                      |
| `documentationUrl`<br/>*HttpUrl*                       | A URL to additional image or product documentation. Used in labeling.                                                               |                                             | `https://docs.example.com/my-image`                                                                                                      |
| `subpath`<br/>*string*                                 | The subpath relative from the project root directory where the image's versions and templates are stored.                           | `<name>`                                    | `my_image`, `my/image`                                                                                                                   |
| `extraRegistries`<br/>*[Registry](#registry) array*    | Additional registries to push this image to in addition to the global `registries` in [bakery.yaml](#bakery-configuration).         | `[]`                                        | <pre>- host: docker.io<br/>  namespace: posit</pre>                                                   |
| `overrideRegistries`<br/>*[Registry](#registry) array* | If set, overrides the global `registries` in [bakery.yaml](#bakery-configuration) for this image with the given list of registries. | `[]`                                        | <pre>- host: docker.io<br/>  namespace: posit</pre>                                                   |
| `tagPatterns`<br/>*[TagPattern](#tagpattern) array*    | The list of tag patterns to apply to all versions of this image.                                                                    | [Default Tag Patterns](#default-patterns)   | <pre>- patterns: ["{{ Version }}"]<br/>  only:<br/>    - "primaryOS"<br/>    - "primaryVariant"</pre> |
| `variants`<br/>*[ImageVariant](#imagevariant) array*   | The list of variants for the image. Each variant should have its own `Containerfile`.                                               | [Default Variants](#default-image-variants) | `- name: Minimal`                                                                                                                        |
| `versions`<br/>*[ImageVersion](#imageversion) array*   | *(Required)* The list of versions for the image. Each version should have its own directory under the image's `subpath`.            | `[]`                                        | `- name: 2025.07.0`                                                                                                                      |
| `options`<br/>*[ToolOptions](#tooloptions) array*      | A list of options to pass to a supported tool when performing an action against the image.                                          | `[]`                                        | <pre>- tool: goss<br/>  wait: 10<br/>  command: "my-custom command"</pre>                             |

#### Example Image

```yaml
images:
  - name: workbench
    displayName: Posit Workbench
    description: A containerized image of Posit Workbench, a remote development environment for data scientists.
    documentationUrl: https://docs.posit.co/ide/
    variants:
      - name: Standard
        extension: std
        tagDisplayName: std
        primary: true
        options:
          - tool: goss
            wait: 20
            command: rserver start
      - name: Minimal
        extension: min
        tagDisplayName: min
    versions:
      - name: "2025.05.1+513.pro3"
        subpath: "2025.05.1"
        latest: true
        os:
          - name: Ubuntu 24.04
            primary: true
            extension: ubuntu2404
            tagDisplayName: ubuntu24.04
          - name: Ubuntu 22.04
            extension: ubuntu2204
            tagDisplayName: ubuntu22.04
      - name: "2024.12.1+563.pro2"
        subpath: "2024.12.1"
        os:
          - name: Ubuntu 22.04
            extension: ubuntu2204
            tagDisplayName: ubuntu22.04
```

### ImageVariant

An ImageVariant represents a variant of an image, such as standard or minimal builds. Each variant is expected have its
own `Containerfile.<os>.<variant>`.

| Field                                | Description                                                                                                                                                          | Default Value                                                                                          | Example                                                                                                                    |
|--------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------|
| `name`<br/>*string*                  | *(Required)* The full human-readable name of the image variant. Used in labeling.                                                                                    |                                                                                                        | `Standard`, `Minimal`                                                                                                      |
| `primary`<br/>*bool*                 | Indicates if this is the primary variant of the image. Only one variant should be marked as primary.                                                                 | `false`                                                                                                | `true`                                                                                                                     |
| `extension`<br/>*string*             | The file extension for the `Containerfile` for this variant.                                                                                                         | `name` with special characters removed and lower-cased.                                                | `min`, `minimal`                                                                                                           |
| `tagDisplayName`<br/>*string*        | The display name of the variant to be used in tags. This value is passed in as the `{{ Variant }}` variable in Jinja2 when rendering [TagPatterns](#tagpattern).     | `name` with disallowed tag characters changed to "-" and lower-cased.                                  | `min`, `minimal`                                                                                                           |
| `tagPatterns`<br/>*TagPattern array* | The list of tag patterns to apply to all image targets of this image variant. These patterns are merged with those defined for the variant's parent [Image](#image). | `[]`                                                                                                   | <pre>- patterns: [minimal-"{{ Version }}"]<br/>  only:<br/>    - "primaryOS"<br/></pre> |
| `options`<br/>*ToolOptions array*    | A list of options to pass to a supported tool when performing an action against this image variant.                                                                  | <pre>- tool: goss<br/>  wait: 0<br/>  command: sleep infinity</pre> | <pre>- tool: goss<br/>  wait: 10<br/>  command: "my-custom command"</pre>               |

#### Default Image Variants
By default, the following image variants will be used for an [Image](#image) if no `variants` are otherwise specified for the [Image](#image).

```yaml
variants:
  - name: Standard
    extension: std
    tagDisplayName: std
    primary: true
  - name: Minimal
    extension: min
    tagDisplayName: min
```

### ImageVersion

An ImageVersion represents a specific version of an image. Each version should be rendered from templates using the `bakery create version` command.

| Field                                                  | Description                                                                                                                                                                                                                                                          | Default Value                                                                                                                   | Example                                                                                |
|--------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| `name`<br/>*string*                                    | *(Required)* The full name of the version.                                                                                                                                                                                                                           |                                                                                                                                 | `2025.05.1+513.pro3`, `2025.04.2-8`, `2025.07.0`                                       |
| `subpath`<br/>*string*                                 | The subpath relative from the image's `subpath` where this version's files are stored.                                                                                                                                                                               | `name` with spaces replaced by "-" and lower-cased.                                                                             | `2025.05.1`, `2025.04.2`, `2025.07.0`                                                  |
| `extraRegistries`<br/>*[Registry](#registry) array*    | Additional registries to push this image version to in addition to the global `registries` in [bakery.yaml](#bakery-configuration) and `extraRegistries` or `overrideRegistries` if set in the parent [Image](#image). Cannot be set with `overrideRegistries`.      | `[]`                                                                                                                            | <pre>- host: docker.io<br/>  namespace: posit</pre> |
| `overrideRegistries`<br/>*[Registry](#registry) array* | If set, overrides the global `registries` in [bakery.yaml](#bakery-configuration) and `extraRegistries` or `overrideRegistries` if set in the parent [Image](#image) for this image version with the given list of registries. Cannot be set with `extraRegistries`. | `[]`                                                                                                                            | <pre>- host: docker.io<br/>  namespace: posit</pre> |
| `latest`<br/>*bool*                                    | Indicates if this is the latest version of the image. Only one version should be marked as latest.                                                                                                                                                                   | `false`                                                                                                                         | `true`                                                                                 |
| `os`<br/>*[ImageVersionOS](#imageversionos) array*     | The list of operating systems supported by this image version. Each operating system should have its own `Containerfile.<os>.<variant>`.                                                                                                                             | If another image was previously marked as `latest`, `bakery create version` will copy its `os` list by default. Otherwise `[]`. | <pre>- name: Ubuntu 22.04</pre>                     |

#### Example Image Version

```yaml
versions:
  - name: "2025.05.1+513.pro3"
    subpath: "2025.05.1"
    latest: true
    os:
      - name: Ubuntu 22.04
```

### ImageVersionOS

An ImageVersionOS represents an operating system supported by an image version.

| Field                         | Description                                                                                                                                                          | Default Value                                                         | Example                     |
|-------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------|-----------------------------|
| `name`<br/>*string*           | *(Required)* The name and version of the image's base operating system.                                                                                              |                                                                       | `Ubuntu 22.04`, `Debian 11` |
| `primary`<br/>*bool*          | Indicates if this is the primary operating system of the image version.                                                                                              | `true` if only one OS is defined, otherwise `false`.                  | `true`                      |
| `extension`<br/>*string*      | The file extension for the `Containerfile.<os>.<variant>` for this operating system.                                                                                 | `name` with special characters removed and lower-cased.               | `ubuntu2204`, `debian11`    |
| `tagDisplayName`<br/>*string* | The display name of the operating system to be used in tags. This value is passed in as the `{{ OS }}` variable in Jinja2 when rendering [TagPatterns](#tagpattern). | `name` with disallowed tag characters changed to "-" and lower-cased. | `ubuntu-22.04`, `debian-11` |

#### Example Image Version OS

```yaml
os:
  - name: Ubuntu 22.04
    primary: true
    extension: ubuntu2204
    tagDisplayName: ubuntu22.04
```

### Dependency

Dependencies represents a list software dependencies that is installed in a specific image version.

Each Dependency defines the dependency type, as well as the versions of the dependency that will be installed.
The versions can be defined explicitly as an array of strings, or in terms of a version constraint.

| Field | Description | Default Value | Example |
|-------|-------------|---------------|---------|
| `dependency`<br/>*string* | *(Required)* The name of the dependency. | | `R`, `python`, `quarto` |
| `versions`<br/>*array* or *map* | *(Required)* An array of explicit, exact versions, or a `VersionConstraint` map.  | | <pre>- "4.5.1"<br/>- "4.4.2.3"</pre> |

#### VersionConstraint

| Field | Description | Default Value | Example |
|-------|-------------|---------------|---------|
| `latest`<br/>*bool* | Include the latest version. | | `true`, `false` |
| `count`<br/>*int* | Number of minor versions to include. | | `2`, `4` |
| `max`<br/>*string* | Maximum version to include. | | `3.13.7`, `3.11`, `3` |
| `min`<br/>*string* | Minimum version to include. | | `4.2.1`, `4.3`, `4` |

At least one of `latest` or `max` must be specified.

If `latest` is `true` and no other fields are set, `count` defaults to `1`.

#### Example Dependency Version List

```yaml
# Install specific versions of Python and R
dependencies:
  - dependency: python
    versions:
      - "3.13.7"
      - "3.12.5"
  - dependency: R
    versions: ["4.5.1", "4.4.2", "3.6.3"]
```

#### Example Dependency Version Constraint

```yaml
dependencies:
  # Install the latest patch of python minor versions from 3.9 to 3.11, inclusive
  - depencency: python
    versions:
      max: "3.11"
      min: "3.9"
  # Pin the maximum R version to 4.4.2, and install 3 minor versions
  - dependency: R
    versions:
      max: "4.4.2"
      count: 3
  # Install the 2 most recent minor versions of quarto, including the pre-release version
  - dependency: quarto
    prerelease: true
    versions:
      latest: true
      count: 2
```

## Other Types

### NameEmail

A NameEmail represents a name and email address pair.

| Field                | Description              | Example              |
|----------------------|--------------------------|----------------------|
| `name`<br/>*string*  | The name of the person.  | Jane Doe             |
| `email`<br/>*string* | The email of the person. | jane.doe@example.com |

### TagPattern

A TagPattern represents a pattern for tagging images. It can include placeholders that are replaced with actual values when generating tags.

| Field                                                    | Description                                                                                                                                           |
|----------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| `patterns`<br/>*string array*                            | *(Required)* The list of Jinja2 patterns for the tag.                                                                                                 |
| `only`<br/>*[TagPatternFilter](#tagpatternfilter) array* | *(Optional)* A list of conditionals to restrict what image targets the tag `patterns` apply to. By default, patterns will apply to all image targets. |

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
