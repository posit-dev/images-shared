# Configuration

This document provides an overview of the configuration schema for Bakery, a tool for managing container images. The configuration is defined in a YAML file named `bakery.yaml`. A template for this file can be created using `bakery create project`.

Fields marked as “*Required*” must be provided in the configuration file.

## Bakery Configuration

The top-level Bakery configuration, `bakery.yaml`, is represented in the table below.

[TABLE]

### Example Configuration

``` yaml
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
    dependencyConstraints:
      - dependency: python
        constraint:
          latest: true
      - dependency: R
        constraint:
          max: "4.4"
          count: 1
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
        dependencies:
          - dependency: python
            version: "3.12.11"
          - dependency: R
            version: "4.4.3"
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
        dependencies:
          - dependency: python
            version: "3.12.9"
          - dependency: R
            version: "4.4.2"
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

A Repository stores the metadata of the parent source code repository of the project. It is primarily used for labeling images.

[TABLE]

### BaseRegistry

A BaseRegistry represents a container image registry. It does not specify the repository (name) for the image.

[TABLE]

### Registry

A Registry represents a container image registry and includes the name or repository of the image. It is a subclass of BaseRegistry.

This type can be specified for an image or version, but cannot be specified at the top level of the bakery configuration.

A common use is pushing images to a repository name that is different from the name of the image.

[TABLE]

## Image Specification Types

### Image

An Image represents a container image managed by the project. Each image has one or more versions and optionally can have one or more variants and operating systems. New images can be created using the `bakery create image` command.

[TABLE]

#### Example Image

``` yaml
images:
  - name: workbench
    displayName: Posit Workbench
    description: A containerized image of Posit Workbench, a remote development environment for data scientists.
    documentationUrl: https://docs.posit.co/ide/
    dependencyConstraints:
      - dependency: python
        constraint:
          latest: true
      - dependency: R
        constraint:
          max: "4.4"
          count: 2
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
        subpath: "2025.05"
        latest: true
        dependencies:
          - dependency: python
            version: "3.12.11"
          - dependency: R
            version: "4.4.3"
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
        dependencies:
          - dependency: python
            version: "3.12.9"
          - dependency: R
            version: "4.4.2"
        os:
          - name: Ubuntu 22.04
            extension: ubuntu2204
            tagDisplayName: ubuntu22.04
```

### ImageDevelopmentVersion

An `ImageDevelopmentVersion` defines an ephemeral version resolved at build time. Unlike static `versions`, it is not stored on disk — Bakery fetches the version string (and optionally download URLs) from an external source each time a dev build runs. Development versions are included when `--dev-versions include` or `--dev-versions only` is passed to `bakery build` or `bakery ci matrix`.

Each entry carries a `sourceType` discriminator that selects the resolution strategy.

**Common fields** (all sourceTypes):

[TABLE]

#### `sourceType: stream` — Product Channel

Resolves the version from a Posit product release channel. The artifact download URL is fetched from the channel’s CDN and injected into the Containerfile template.

[TABLE]

**Example:**

``` yaml
devVersions:
  - sourceType: stream
    product: workbench
    channel: daily
    overrideRegistries:
      - host: ghcr.io
        namespace: posit-dev
        repository: workbench-preview
    os:
      - name: Ubuntu 24.04
        primary: true
        platforms:
          - linux/amd64
          - linux/arm64
      - name: Ubuntu 22.04
```

#### `sourceType: dependency` — Dependency Prerelease

Resolves the version via the dependency constraint system rather than a product channel. The Containerfile template is responsible for constructing the download URL from `Image.Version` and any `values` passed.

[TABLE]

**Example:**

``` yaml
devVersions:
  - sourceType: dependency
    dependency: positron
    prerelease: true
    channel: daily
    values:
      POSITRON_CHANNEL: dailies
    overrideRegistries:
      - host: ghcr.io
        namespace: posit-dev
        repository: workbench-positron-init-preview
    os:
      - name: Ubuntu 24.04
        primary: true
        platforms:
          - linux/amd64
          - linux/arm64
```

### ImageVariant

An ImageVariant represents a variant of an image, such as standard or minimal builds. Each variant is expected have its own `Containerfile.<os>.<variant>`.

[TABLE]

#### Common Image Variants

By default, the image variants for an [Image](#image) will be set to an empty list `[]` if no `variants` are otherwise specified for the [Image](#image).

A common pattern is to build a minimal image containing fewer dependencies, and a standard image that builds dependencies into the container.

``` yaml
variants:
  - name: Standard
    extension: std
    tagDisplayName: std
    primary: true
  - name: Minimal
    extension: min
    tagDisplayName: min
```

### ImageMatrix

An ImageMatrix generates multiple image versions from combinations of dependency versions and custom values. This is useful when you need to build an image that lacks a singular component to version on or that requires different dependency combinations (e.g., multiple R and Python version combinations).

**Note:** An image can have either `versions` or `matrix`, but not both.

[TABLE]

At least one of `dependencyConstraints`, `dependencies`, or `values` must be defined.

#### Example ImageMatrix

``` yaml
images:
  - name: r-session
    displayName: R Session
    matrix:
      namePattern: "r{{ Dependencies.R }}-py{{ Dependencies.python }}"
      subpath: matrix
      dependencies:
        - dependency: R
          versions: ["4.4.3", "4.3.3"]
        - dependency: python
          versions: ["3.12", "3.11"]
      os:
        - name: Ubuntu 24.04
          primary: true
          extension: ubuntu2404
          tagDisplayName: ubuntu24.04
```

This generates four image versions: - `r4.4.3-py3.12` - `r4.4.3-py3.11` - `r4.3.3-py3.12` - `r4.3.3-py3.11`

#### Latest Tag Selection

When every version-bearing axis (each `dependency`, each `dependencyConstraint` after resolution, and each list-typed entry in `values`) contains version-parseable strings, Bakery automatically marks the cartesian-product row at the maximum version of every axis as the “latest” combination. That row inherits the same `latest`-family tags applied to non-matrix versions — including the bare `latest` tag when paired with the primary OS and primary variant.

In the example above, the latest combination is `r4.4.3-py3.12`. Built against the primary OS and primary variant (if any), it would receive `latest`, `<os>`, `<variant>`, and `<os>-<variant>` tags in addition to its existing matrix tags.

If any axis has a non-version-parseable entry (e.g., a list-typed `values` axis containing `["alpha", "beta"]`), Bakery emits a warning naming the offending axis and value, and the matrix produces no `latest`-family tags. Scalar (non-list) `values` are constant across the cartesian product and do not affect the latest selection.

### DependencyConstraint

A DependencyConstraint represents a software dependency installed in a specific image.

At the image level, these are specified through a VersionConstraint.

[TABLE]

> **NOTE:**
>
> The `quarto` and `positron` dependency types support an additional `prerelease` field (default: `false`). When `true`, prerelease versions are included in the version calculation.

Each Dependency defines the dependency type, as well as the versions of the dependency that will be installed. The versions can be defined explicitly as an array of strings, or in terms of a version constraint.

#### VersionConstraint

[TABLE]

At least one of `latest` or `max` must be specified.

If `latest` is `true` and no other fields are set, `count` defaults to `1`.

#### Example Dependency Version Constraint

``` yaml
dependencyConstraints:
  # Install the latest patch of python minor versions from 3.9 to 3.11, inclusive
  - dependency: python
    constraint:
      max: "3.11"
      min: "3.9"
  # Pin the maximum R version to 4.4.2, and install 3 minor versions
  - dependency: R
    constraint:
      max: "4.4.2"
      count: 3
  # Install the 2 most recent minor versions of quarto, including the pre-release version
  - dependency: quarto
    prerelease: true
    constraint:
      latest: true
      count: 2
```

### ImageVersion

An ImageVersion represents a specific version of an image. Each version should be rendered from templates using the `bakery create version` command.

[TABLE]

#### Example Image Version

``` yaml
versions:
  - name: "2025.05.1+513.pro3"
    subpath: "2025.05"
    latest: true
    dependencies:
      - dependency: python
        version: "3.12.11"
      - dependency: R
        version: "4.4.3"
    os:
      - name: Ubuntu 22.04
    values:
      go_version: "1.25.2"
```

### ImageVersionOS

An ImageVersionOS represents an operating system supported by an image version.

[TABLE]

#### Example Image Version OS

``` yaml
os:
  - name: Ubuntu 22.04
    primary: true
    extension: ubuntu2204
    tagDisplayName: ubuntu22.04
```

### DependencyVersions

At the version level, dependency versions are specified explicitly.

[TABLE]

You must specify either `version` or `versions`.

#### Example Dependency Version List

``` yaml
# Install specific versions of Python and R
dependencies:
  - dependency: python
    versions:
      - "3.13.7"
      - "3.12.5"
  - dependency: R
    versions: ["4.5.1", "4.4.2", "3.6.3"]
  - dependency: quarto
    version: "1.7.34"
```

## Other Types

### NameEmail

A NameEmail represents a name and email address pair.

[TABLE]

### TagPattern

A TagPattern represents a pattern for tagging images. It can include placeholders that are replaced with actual values when generating tags.

[TABLE]

#### Pattern Templating

All [TagPattern](#tagpattern) `patterns` should be valid Jinja2 template strings.

The following variables are available for use in `patterns`: - `{ Version }`: The version of the image. - `{ OS }`: The operating system of the image. - `{ Variant }`: The variant of the image. - `{ Name }`: The name of the image.

In addition to the default Jinja2 filter functions, the following custom filters are also available for use in `patterns`: - `tagSafe`: Replaces disallowed characters in a tag with a hyphen (`-`). Disallowed characters are any characters other than alphanumeric characters, `.`, `_`, or `-`. - `stripMetadata`: Removes trailing metadata suffixes in a version that start with `-` or `+`. For example, `1.2.3-rc1` becomes `1.2.3`. - `condense`: Removes , `.`, and `-` characters. - `regexReplace <find> <replace>`: Uses `re.sub` to replace occurrences of the `find` regex pattern with the `replace` string.

#### Default Patterns

By default, the following tag patterns will be used for an [Image](#image) if no `tagPatterns` are otherwise specified for the [Image](#image) or [ImageVariant](#imagevariant). These patterns mirror the behavior noted in the [Image Tags](index.llms.md#image-tags) section of the README.

``` yaml
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

[TABLE]

#### SociOptions

A SociOption configures [SOCI](https://github.com/awslabs/soci-snapshotter) (Seekable OCI) index generation for an image target. SOCI indexes let container runtimes lazily pull image layers, reducing startup latency for large images.

SOCI options can be set in the `options` array of an [Image](#image) or an [ImageVariant](#imagevariant). When both are present, the variant’s options are merged over the image’s options, with any field not explicitly set on the variant inheriting the image-level value. SOCI conversion runs as a post-build step via `bakery soci convert` (standalone) or as part of `bakery ci publish` (config-driven), and only acts on targets where `enabled` is `true`.

[TABLE]

##### Example SociOptions

``` yaml
images:
  - name: workbench
    options:
      - tool: soci
        enabled: true
        min_layer_size: 10485760
    variants:
      - name: Standard
        extension: std
        tagDisplayName: std
        primary: true
        options:
          # Override the image-level SOCI settings for this variant only.
          - tool: soci
            enabled: true
            span_size: 4194304
            platforms:
              - linux/amd64
              - linux/arm64
```

### DevBuildSpec

A DevBuildSpec is a typed payload passed to the `--dev-spec` CLI option to configure development (daily) version builds. It supports either a dispatch-pinned version or a branch-targeted discovery build. At least one of `version` or `release_branch` must be set.

[TABLE]

#### Example DevBuildSpec Usage

``` bash
# Build a specific pinned development version
bakery build --dev-spec '{"version": "2026.07.0-dev+345-gabc1234"}'

# Build from the "apple-blossom" release branch
bakery build --dev-spec '{"release_branch": "apple-blossom"}'
```

## See Also

- [Templating Documentation](templating.llms.md) — Jinja2 macros and variables available in image templates
- [Architecture Diagrams](architecture.llms.md) — Detailed tool behavior and flow diagrams
- [Bakery Examples](https://github.com/posit-dev/images-examples/tree/main/bakery) — Real-world `bakery.yaml` files and step-by-step tutorials

Back to top
