# bakery clean temp-registry

# bakery clean temp-registry

Cleans up temporary images in an external registry

``` bash
bakery clean temp-registry [OPTIONS] REGISTRY
```

⚠️ **This command currently only supports GHCR registries.** ⚠️

This command is intended to be used as a cleanup utility for temporary images created with the `bakery build --temp-registry <registry>` option. By default, it will remove all images older than 3 days. Images are assumed to be created by Bakery in the registry namespace `<registry>/<image-name>/tmp`. If the `--image-name` filter is not provided, all images for the project will be cleaned.

    Usage: bakery clean temp-registry [OPTIONS] REGISTRY

      Cleans up temporary images in an external registry

      ⚠️ **This command currently only supports GHCR registries.** ⚠️

      This command is intended to be used as a cleanup utility for temporary
      images created with the `bakery build --temp-registry <registry>` option. By
      default, it will remove all images older than 3 days. Images are assumed to
      be created by Bakery in the registry namespace `<registry>/<image-
      name>/tmp`. If the `--image-name` filter is not provided, all images for the
      project will be cleaned.

    Arguments:
      REGISTRY  GHCR registry to clean temporary images in *(ex. ghcr.io/my-org)*.
                [required]

    Options:
      --context DIRECTORY             The root path to use. Defaults to the
                                      current working directory where invoked.
                                      [default: (.)]
      --untagged / --no-untagged      Prune dangling images.  [default: no-
                                      untagged]
      --older-than INTEGER            Prune caches older than specified days.
      --image-name TEXT               The image name or a regex pattern to isolate
                                      clean operations to.
      --dev-versions [include|exclude|only]
                                      Include or exclude development version
                                      temporary images.  [default: exclude]
      --dev-channel [release|preview|daily]
                                      Filter development versions to a specific
                                      release channel.
      --matrix-versions [include|exclude|only]
                                      Include or exclude matrix version temporary
                                      images.  [default: exclude]
      --dry-run                       If set, print what would be deleted and
                                      exit.
      -v, --verbose                   Enable debug logging
      -q, --quiet                     Supress all output except errors
      --help                          Show this message and exit.

## Arguments

`REGISTRY``:`` ``TEXT`  
Required.

## Options

`--context``:`` ``DIRECTORY`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory where invoked.

`--untagged, --no-untagged`  
Prune dangling images.

`--older-than``:`` ``INTEGER`  
Prune caches older than specified days.

`--image-name``:`` ``TEXT`  
The image name or a regex pattern to isolate clean operations to.

`--dev-versions``:`` ``CHOICE`` ``=`` ``DevVersionInclusionEnum.EXCLUDE`  
Include or exclude development version temporary images.

`--dev-channel``:`` ``CHOICE`  
Filter development versions to a specific release channel.

`--matrix-versions``:`` ``CHOICE`` ``=`` ``MatrixVersionInclusionEnum.EXCLUDE`  
Include or exclude matrix version temporary images.

`--dry-run`  
If set, print what would be deleted and exit.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

Back to top
