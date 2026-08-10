# bakery

# bakery

A tool for building, testing, and managing container images

``` bash
bakery
```

    Usage: bakery [OPTIONS] COMMAND [ARGS]...

      A tool for building, testing, and managing container images

    Options:
      --install-completion  Install completion for the current shell.  [default:
                            <object object at 0x7f3ab64d8c10>]
      --show-completion     Show completion for the current shell, to copy it or
                            customize the installation.  [default: <object object
                            at 0x7f3ab64d8c10>]
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

Back to top
