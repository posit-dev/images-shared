# bakery build

# bakery build

Build images using buildkit bake (aliases: b, bake)

``` bash
bakery build [OPTIONS]
```

    Usage: bakery build [OPTIONS]

      Build images using buildkit bake (aliases: b, bake)

    Options:
      --context DIRECTORY             The root path to use. Defaults to the
                                      current working directory where invoked.
                                      [default: (.)]
      --strategy [build|bake]         The strategy to use when building the image.
                                      'bake' requires Docker Buildkit and builds
                                      images in parallel. 'build' can use generic
                                      container builders, such as Podman, and
                                      builds images concurrently, bounded by
                                      --jobs.  [default: bake]
      --fail-fast                     Terminate builds on the first failure.
      --retry INTEGER RANGE           Number of times to retry a failed build.
                                      [default: 0; x>=0]
      -j, --jobs INTEGER RANGE        Maximum number of targets to build
                                      concurrently for '--strategy build' (ignored
                                      for '--strategy bake'). Defaults to the
                                      BAKERY_MAX_CONCURRENCY env var or a built-in
                                      default.  [x>=1]
      --plan                          Print the bake plan and exit.
      --load / --no-load              Load the image to Docker after building.
                                      [default: load]
      --push / --no-push              Push the image to its registry tags after
                                      building.  [default: no-push]
      --clean / --no-clean            Clean up intermediary and temporary files
                                      after building. Disable for debugging.
                                      [default: clean]
      --metadata-file PATH            The path to write JSON build metadata to
                                      once builds are finished.
      --pull / --no-pull              Always pull the latest version of base
                                      images.  [default: no-pull]
      --cache / --no-cache            Enable layer caching for image builds.
                                      [default: cache]
      --cache-registry TEXT           External registry to use for layer caching.
      --temp-registry TEXT            Temporary registry to use for multiplatform
                                      split/merge builds.
      --image-name TEXT               The image name or a regex pattern to isolate
                                      builds to.
      --image-version TEXT            The image version or version prefix to
                                      isolate builds to.
      --image-variant TEXT            The image type to isolate builds to.
      --image-os TEXT                 The image OS name or a regex pattern to
                                      isolate builds to.
      --image-platform TEXT           The image platform(s) to isolate builds to,
                                      e.g. 'linux/amd64'. Image build targets
                                      incompatible with the given platform(s) will
                                      be skipped.
      --dev-versions [include|exclude|only]
                                      Include or exclude development version
                                      builds defined in config.  [default:
                                      exclude]
      --dev-channel [release|preview|daily]
                                      Filter development versions to a specific
                                      release channel.
      --matrix-versions [include|exclude|only]
                                      Include or exclude versions defined in image
                                      matrix.  [default: exclude]
      --latest                        Build only the latest version of each image.
                                      Development versions are ignored by this
                                      filter.
      --dev-spec TEXT                 JSON spec for a dispatched dev build. Ex:
                                      '{"version": "2026.05.0-dev+185-gSHA",
                                      "channel": "daily"}'  [env var:
                                      BAKERY_DEV_SPEC]
      -v, --verbose                   Enable debug logging
      -q, --quiet                     Supress all output except errors
      --help                          Show this message and exit.

## Options

`--context``:`` ``DIRECTORY`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory where invoked.

`--strategy``:`` ``CHOICE`` ``=`` ``ImageBuildStrategy.BAKE`  
The strategy to use when building the image. `bake` requires Docker Buildkit and builds images in parallel. `build` can use generic container builders, such as Podman, and builds images concurrently, bounded by `--jobs`.

`--fail-fast`  
Terminate builds on the first failure.

`--retry``:`` ``INTEGER RANGE`` ``=`` ``0`  
Number of times to retry a failed build.

`-j, --jobs``:`` ``INTEGER RANGE`  
Maximum number of targets to build concurrently for `--strategy build` (ignored for `--strategy bake`). Defaults to the BAKERY_MAX_CONCURRENCY env var or a built-in default.

`--plan`  
Print the bake plan and exit.

`--load, --no-load`  
Load the image to Docker after building.

`--push, --no-push`  
Push the image to its registry tags after building.

`--clean, --no-clean`  
Clean up intermediary and temporary files after building. Disable for debugging.

`--metadata-file``:`` ``PATH`  
The path to write JSON build metadata to once builds are finished.

`--pull, --no-pull`  
Always pull the latest version of base images.

`--cache, --no-cache`  
Enable layer caching for image builds.

`--cache-registry``:`` ``TEXT`  
External registry to use for layer caching.

`--temp-registry``:`` ``TEXT`  
Temporary registry to use for multiplatform split/merge builds.

`--image-name``:`` ``TEXT`  
The image name or a regex pattern to isolate builds to.

`--image-version``:`` ``TEXT`  
The image version or version prefix to isolate builds to.

`--image-variant``:`` ``TEXT`  
The image type to isolate builds to.

`--image-os``:`` ``TEXT`  
The image OS name or a regex pattern to isolate builds to.

`--image-platform``:`` ``TEXT`  
The image platform(s) to isolate builds to, e.g. `linux/amd64`. Image build targets incompatible with the given platform(s) will be skipped.

`--dev-versions``:`` ``CHOICE`` ``=`` ``DevVersionInclusionEnum.EXCLUDE`  
Include or exclude development version builds defined in config.

`--dev-channel``:`` ``CHOICE`  
Filter development versions to a specific release channel.

`--matrix-versions``:`` ``CHOICE`` ``=`` ``MatrixVersionInclusionEnum.EXCLUDE`  
Include or exclude versions defined in image matrix.

`--latest`  
Build only the latest version of each image. Development versions are ignored by this filter.

`--dev-spec``:`` ``TEXT`  
JSON spec for a dispatched dev build. Ex: `{"version": "2026.05.0-dev+185-gSHA", "channel": "daily"}` Environment variable: `BAKERY_DEV_SPEC`.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

Back to top
