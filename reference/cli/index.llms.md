# bakery

# bakery

A tool for building, testing, and managing container images

``` bash
bakery [OPTIONS] COMMAND [ARGS]...
```

    Usage: bakery [OPTIONS] COMMAND [ARGS]...

      A tool for building, testing, and managing container images

    Options:
      --install-completion  Install completion for the current shell.
      --show-completion     Show completion for the current shell, to copy it or
                            customize the installation.
      --help                Show this message and exit.

    Commands:
      build       Build images using buildkit bake (aliases: b, bake)
      version     Show the Posit Bakery version
      run         Run extra tools/commands against images (aliases: r)
      create      Create new projects, images, and versions (aliases: c, new)
      update      Update managed files and configurations (aliases: u, up)
      remove      Remove images and versions from the project (aliases: rm, r)
      get         Get information about the bakery configuration
      ci          Construct a CI matrix from the project.
      clean       Cleaning utilities for remote build caches
      dgoss       Run Goss tests against container images
      hadolint    Lint Containerfiles using hadolint
      imagetools  Merge and SOCI-convert multi-platform images (ORAS + SOCI)
      wizcli      Scan container images for vulnerabilities with WizCLI

## Options

`--install-completion`  
Install completion for the current shell.

`--show-completion`  
Show completion for the current shell, to copy it or customize the installation.

## Commands

`build`  
[Build images using buildkit bake (aliases: b, bake)](../../reference/cli/build.llms.md)

`version`  
[Show the Posit Bakery version](../../reference/cli/version.llms.md)

`run`  
[Run extra tools/commands against images (aliases: r)](../../reference/cli/run.llms.md)

`create`  
[Create new projects, images, and versions (aliases: c, new)](../../reference/cli/create.llms.md)

`update`  
[Update managed files and configurations (aliases: u, up)](../../reference/cli/update.llms.md)

`remove`  
[Remove images and versions from the project (aliases: rm, r)](../../reference/cli/remove.llms.md)

`get`  
[Get information about the bakery configuration](../../reference/cli/get.llms.md)

`ci`  
[Construct a CI matrix from the project.](../../reference/cli/ci.llms.md)

`clean`  
[Cleaning utilities for remote build caches](../../reference/cli/clean.llms.md)

`dgoss`  
[Run Goss tests against container images](../../reference/cli/dgoss.llms.md)

`hadolint`  
[Lint Containerfiles using hadolint](../../reference/cli/hadolint.llms.md)

`imagetools`  
[Merge and SOCI-convert multi-platform images (ORAS + SOCI)](../../reference/cli/imagetools.llms.md)

`wizcli`  
[Scan container images for vulnerabilities with WizCLI](../../reference/cli/wizcli.llms.md)

Back to top
