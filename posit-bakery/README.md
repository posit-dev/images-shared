# Bakery

The [bakery](./posit_bakery/) command line interface (CLI) binds together various [tools](#3rd-party-tools) to manage a matrixed build of container images.

## Documentation

Full documentation is available at **[posit-dev.github.io/images-shared](https://posit-dev.github.io/images-shared/)**.

## Prerequisites

* [python](https://docs.astral.sh/uv/guides/install-python/)
* [uv](https://docs.astral.sh/uv/getting-started/installation/)
* [docker buildx bake](https://github.com/docker/buildx#installing)
* [just](https://just.systems/man/en/prerequisites.html)

### 3rd Party Tools

| Tool                                                                                                                                                                      | Used By                         | Purpose                                                            |
|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------------------------|:-------------------------------------------------------------------|
| [docker buildx bake](https://github.com/docker/buildx#installing)                                                                                                         | `bakery build --strategy bake`  | Build containers in parallel                                       |
| [docker](https://github.com/docker/buildx#installing), [podman](https://podman-desktop.io/docs/installation), or [nerdctl](https://github.com/containerd/nerdctl#install) | `bakery build --strategy build` | Build containers in series                                         |
| [dgoss](https://github.com/goss-org/goss#installation)                                                                                                                    | `bakery run dgoss`              | Test container images for expected content & behavior              |
| [hadolint](https://github.com/hadolint/hadolint#install)                                                                                                                  | to be implemented               | Lint Dockerfile/Containerfile                                      |
| [openscap](https://static.open-scap.org/)                                                                                                                                 | to be implemented               | Scan container images for secure configuration and vulnerabilities |
| trivy                                                                                                                                                                      | to be implemented               | Scan container images for vulnerabilities                          |
| wizcli                                                                                                                                                                     | to be implemented               | Scan container images for vulnerabilities                          |

## Installation

Install `bakery` using `uv tool`:

```bash
uv tool install 'git+https://github.com/posit-dev/images-shared.git@main#subdirectory=posit-bakery&egg=posit-bakery'
```

## Examples

See the [Bakery Examples](https://github.com/posit-dev/images-examples/tree/main/bakery) repository for step-by-step tutorials on creating and managing container image projects with Bakery.

## Development

### Development Prerequisites

- [just](https://just.systems/man/en/)

    ```bash
    # Show all the just recipes
    just
    ```

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
