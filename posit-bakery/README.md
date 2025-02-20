# Bakery

The [bakery](./posit-bakery/) command line interface (CLI) binds together various [tools](#3rd-party-tools) to manage a matrixed build of container images.

## Getting Started

### Prerequisites

| Tool | Purpose |
|:-----|:--------|
| [pipx](https://pipx.pypa.io/stable/installation/) | Installation and environment isolation of `bakery` tool |
| [GitHub CLI (`gh`)](https://github.com/cli/cli#installation) | Used to fetch artifacts, such as `pti`, from private repositories |

### 3rd Party Tools

Bakery integrates several tools

| Tool | Used By | Purpose |
|:-----|:--------|:--------|
| [docker buildx bake](https://github.com/docker/buildx#installing) | `bakery build` | Build containers in parallel |
| [hadolint](https://github.com/hadolint/hadolint#install) | | Lint Dockerfile/Containerfile |
| [snyk container](https://docs.snyk.io/snyk-cli/install-or-update-the-snyk-cli) | `bakery run snyk` | Scan container images for security vulnerabilities |

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

>[!TIP]
> See the [architecture diagrams](./ARCHITECTURE.md) for detailed tool behavior.

Show the commands available in `bakery`.

```shell
bakery --help
```

### Projects

Bakery establishes a directory structure, referred to as a **project**.
The project configuration is stored in the `config.toml`.

By default, bakery uses the invocation directory as the project **context**.
You can use the `--context` flag to override the default behavior.

```shell
bakery --context /path/to/directory
```

A bakery project can include more than one **image**.
Each image can include have more than one **version**.
The image configuration is stored in a `manifest.toml` file.

```terminal
.
├── config.toml
├── fancy-image/
│   ├── manifest.toml
│   ├── 2024.11.0/
│   ├── 2025.01.0/
│   └── template/
└── more-fancy-image/
    ├── manifest.toml
    ├── 2024.12.0/
    ├── 2024.12.1/
    ├── 2025.02.0/
    └── template/
```

### Step 1. Create a project

* Create a new project

    ```shell
    bakery create project
    ```

    This command will create a new project configuration file in the bakery context.

* Make changes to the `config.toml` file

    Update the contents of the project configuration file
    A new project configuration file includes a default set of values.

### Step 2. Create an image

### Step 3. Create an image version

### Step 4. Build the image

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
