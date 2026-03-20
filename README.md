# Posit Images Shared Tools

> [!IMPORTANT]
> These images are under active development and testing and are not yet supported by Posit.
>
> Please see [rstudio/rstudio-docker-products](https://github.com/rstudio/rstudio-docker-products) for officially supported images.

This repository contains shared build tooling and CI workflows used by the Posit Container Image repositories. **If you want to run pre-built Posit product containers**, see the product repositories instead:

- [Posit Connect](https://github.com/posit-dev/images-connect/blob/main/connect/README.md)
- [Posit Package Manager](https://github.com/posit-dev/images-package-manager/blob/main/package-manager/README.md)
- [Posit Workbench](https://github.com/posit-dev/images-workbench/blob/main/workbench/README.md)
- [Ecosystem overview](https://github.com/posit-dev/images)

## Code Repositories

| Repository | Description |
|:-----------|:------------|
| [images](https://github.com/posit-dev/images) | Posit Container Image Meta Repository |
| [images-connect](https://github.com/posit-dev/images-connect) | Posit Connect Container Images |
| [images-package-manager](https://github.com/posit-dev/images-package-manager) | Posit Package Manager Container Images |
| [images-workbench](https://github.com/posit-dev/images-workbench) | Posit Workbench Container Images |
| [images-examples](https://github.com/posit-dev/images-examples) | Examples for using and extending Posit Container Images |

## Tools

### Bakery

The [bakery](./posit-bakery/) command line interface (CLI) binds together various [tools](./posit-bakery/README.md#3rd-party-tools) to managed a matrix of container image builds.

>[!TIP]
> - [Get started with `bakery`](./posit-bakery/README.md#getting-started)
> - [Bakery Examples](https://github.com/posit-dev/images-examples/tree/main/bakery) — step-by-step tutorials

## GitHub Actions

See [CI Workflows](./CI.md) for shared GitHub Actions workflows used by product image repositories.

### setup-goss

Bakery uses [goss](https://github.com/goss-org/goss) and [dgoss](https://github.com/goss-org/goss/tree/master/extras/dgoss) to define and execute tests that ensure that the container image was built properly.

You can include the [setup-goss](./setup-goss) action in a [GitHub Actions Workflow](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) to automatically install the latest versions of `goss` and `dgoss` in the `tools` directory at the top level of the repository.

## Share your Feedback

We invite you to join us on [GitHub Discussions](https://github.com/posit-dev/images/discussions) to ask questions and share feedback.

## Issues

If you encounter any issues or have any questions, please [open an issue](https://github.com/posit-dev/images-shared/issues). We appreciate your feedback.

## Code of Conduct

We expect all contributors to adhere to the project's [Code of Conduct](CODE_OF_CONDUCT.md) and create a positive and inclusive community.

## License

Posit Container Images and associated tooling are licensed under the [MIT License](LICENSE.md)
