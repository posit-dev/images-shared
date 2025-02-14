# Bakery

The [bakery](./posit-bakery/) command line interface (CLI) binds together various [tools](#3rd-party-tools) to managed a matrixed build of container image.

## Getting Started

### Prerequisites

- [pipx](https://pipx.pypa.io/stable/installation/)
- [GitHub CLI: `gh`](https://github.com/cli/cli#installation) - Pull artifacts from private repos

## Installation

### CLI Installation

1. Authorize w/ GitHub, since the repository is private
    ```bash
    gh auth login
    gh auth setup-git
    ```

2. Install `bakery` using `pipx`
    ```bash
    pipx install 'git+https://github.com/posit-dev/images-shared.git@main#subdirectory=posit-bakery&egg=posit-bakery'
    ```

## Usage

```shell
bakery --help
```

## Image

### Versions

### Targets

#### Minimal Image

#### Standard Image

### Image Tags

Bakery adds the following default tags for all versions of the image:

| Standard Image | Minimal Image | Structure |
|:---------|:--------|:------|
| `2025.01.0-ubuntu-22.04-std` | `2025.01.0-ubuntu-22.04-min` | `<version>-<os>-<type>` |
| `2025.01.0-ubuntu-22.04` | ❌ | `<version>-<os>`|
| *Added if `os == primary_os`* | | |
| `2025.01.0-std` | `2025.01.0-min` | `<version>-<type>` |
| `2025.01.0` | ❌ | `<version>` |

Bakery also adds the following tags to the latest image version:

| Standard Image | Minimal Image | Structure |
|:---------|:--------|:------|
| `ubuntu-22.04-std` | `ubuntu-22.04-min` | `<os>-<type>` |
| `ubuntu-22.04` | ❌ | `<os>` |
| *Added if `os == primary_os`* | | |
| `std` | `min` | `<type>` |
| `latest` | ❌ | `latest` |

## Development

### Development Prerequisites

- [just](https://just.systems/man/en/)
    ```bash
    # Show all the just recipes
    just
    ```

- [poetry](https://python-poetry.org/docs/#installing-with-pipx)

    ```bash
    pipx install 'poetry>=2'
    ```

## Project

## 3rd Party Tools

| Tool | Purpose |
|:-----|:--------|
| [docker buildx bake](https://docs.docker.com/reference/cli/docker/buildx/bake/) | Build containers in parallel |
| [hadolint](https://github.com/hadolint/hadolint) | Lint Dockerfile/Containerfile |
| [snyk container](https://docs.snyk.io/scan-with-snyk/snyk-container) | Scan container images for security vulnerabilities |
