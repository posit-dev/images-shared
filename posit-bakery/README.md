# Bakery

The [bakery](./posit-bakery/) command line interface (CLI) binds together various [tools](#3rd-party-tools) to manage a matrixed build of container images.

## Getting Started

### Prerequisites

* [python](https://docs.astral.sh/uv/guides/install-python/)
* [pipx](https://pipx.pypa.io/stable/installation/)
* [docker buildx bake](https://github.com/docker/buildx#installing)
* [just](https://just.systems/man/en/prerequisites.html)
* [gh](https://github.com/cli/cli#installation) (required while repositories are private)

### 3rd Party Tools

| Tool                                                                                                                                                                      | Used By                         | Purpose                                                            |
|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------------------------|:-------------------------------------------------------------------|
| [docker buildx bake](https://github.com/docker/buildx#installing)                                                                                                         | `bakery build --strategy bake`  | Build containers in parallel                                       |
| [docker](https://github.com/docker/buildx#installing), [podman](https://podman-desktop.io/docs/installation), or [nerdctl](https://github.com/containerd/nerdctl#install) | `bakery build --strategy build` | Build containers in series                                         |
| [dgoss](https://github.com/goss-org/goss#installation)                                                                                                                    | `bakery run dgoss`              | Test container images for expected content & behavior              |
| [hadolint](https://github.com/hadolint/hadolint#install)                                                                                                                  | to be implemented               | Lint Dockerfile/Containerfile                                      |
| [openscap](https://static.open-scap.org/)                                                                                                                                 | to be implemented               | Scan container images for secure configuration and vulnerabilities |
| [trivy](https://trivy.dev/dev/getting-started/installation/)                                                                                                              | to be implemented               | Scan container images for vulnerabilities                          |
| [wizcli](https://github.com/bshandley/wizcli_install)                                                                                                                     | to be implemented               | Scan container images for vulnerabilities                          |

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

# or

bakery help
```

### Step 1. Create a project {#create-project}

* Create a new project

    ```shell
    bakery create project
    ```

    This command creates a new project configuration file in the bakery context.

* Make changes to the `bakery.yaml` file

    Update the contents of the project configuration file.
    A new project configuration file includes a default set of values.

    * Document the source code [Repository](./CONFIGURATION.md#repository)
    * Configure image [Registry](./CONFIGURATION.md#registry) entries to tag and push images to specific registries

### Step 2. Create an image {#create-image}

* Create a new image

    ```shell
    bakery create image fancy-image
    ```

    This command:

    * Creates a directory for the image (`fancy-image` in this example)
    * Creates a `template/` subdirectory
    * Writes a default set of template files
    * Adds the image to the `images` section of the `bakery.yaml` file

* Make changes to the `bakery.yaml` file

    Update the [Image](./CONFIGURATION.md#image) definition.

    * Define [Image Variants](./CONFIGURATION.md#imagevariant)
    * Set [Dependency Constraints](./CONFIGURATION.md#dependencyconstraint)

* Make changes to the default Jinja2 templates

    The default set of templates provide only a basic skeleton of what is required to define and build an image; you will need to modify these generic templates.

    See the [available Jinja variables](./TEMPLATING.md#available-variables) in the templating documentation.

* Add additional templates that will be rendered for each image version

    You can add additional template files that will be created for each new image version.

    Template files must end with the `.jinja2` file extension.

### Step 3. Create an image version {#create-image-version}

* Create a new version of the image

    ```shell
    bakery create version fancy-image 2025.01.0
    ```

    This command

    * Creates a subdirectory for the image version (`fancy-image/2025.01.0` in this example)

      The `--subpath` flag can be used to create the version directory in a different location

    * Updates the `bakery.yaml` file with the new image version
    * Sets the new image to `latest`

      The `--no-mark-latest` flag skips marking the image as the latest

    * Renders the templates created in [Step 2](#step-2-create-an-image), replacing the values

* Make changes to the `bakery.yaml` file

    Update the [ImageVersion](./CONFIGURATION.md#imageversion) definition.

    * Set [Dependency Versions](./CONFIGURATION.md#dependencyversions)

### Step 4. Build the image(s) {#build-images}

* Preview the [bake plan](https://docs.docker.com/build/bake/reference/) [OPTIONAL]

    ```shell
    bakery build --plan
    ```

    The `build --strategy bake` command creates a temporary JSON file that is passed to `docker buildx bake`.

* Build the container images

    ```shell
    bakery build
    ```

### Step 5. Run the tests {#run-tests}

* Run the `dgoss` tests against all the images

    ```shell
    bakery run dgoss
    ```

    You can specify additional run options using Goss options in `bakery.yaml` on a per image or per variant basis.

## Bakery Concepts

### Project Structure

Bakery establishes a directory structure, referred to as a **project**.
The `bakery.yaml` file stores the **project** configuration.

By default, bakery uses the invocation directory as the project **context**.
You can use the `--context` flag to override the default behavior.

```shell
bakery --context /path/to/directory
```

A bakery **project** can include one or more **image**s.
Each **image** can optionally have one or more **variant**s. By default, there are two variants: Standard and Minimal.
Each **image** should have one or more **version**s.
Each **version** can have one or more **OS**es.

```terminal
.
├── bakery.yaml
├── fancy-image/
│   ├── 2024.11.0/
│   ├── 2025.01.0/
│   └── template/
└── more-fancy-image/
    ├── 2024.12.0/
    ├── 2024.12.1/
    ├── 2025.02.0/
    └── template/
```

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
