# bakery run dgoss

# bakery run dgoss

Runs dgoss tests against images in the context path

``` bash
bakery run dgoss [OPTIONS]
```

DEPRECATED: Use `bakery dgoss run` instead. This command will be removed in a future release.

If no options are provided, the command test all images in the project and write test results to the `results/` directory in the context path.

Images are expected to be available to the local Docker daemon. It is advised to run `build` before running dgoss tests.

Requires goss and dgoss to be installed on the system. Paths to the binaries can be set with the `GOSS_BIN` and `DGOSS_BIN` environment variables if not present in the system PATH.

    Usage: bakery run dgoss [OPTIONS]

      Runs dgoss tests against images in the context path

      DEPRECATED: Use 'bakery dgoss run' instead. This command will be removed in a future release.

      If no options are provided, the command test all images in the project and write test results to the `results/`
      directory in the context path.

      Images are expected to be available to the local Docker daemon. It is advised to run `build` before running
      dgoss tests.

      Requires goss and dgoss to be installed on the system. Paths to the binaries can be set with the `GOSS_BIN` and
      `DGOSS_BIN` environment variables if not present in the system PATH.

    Options:
      --context DIRECTORY             The root path to use. Defaults to the
                                      current working directory where invoked.
                                      [default: (.)]
      --image-name TEXT               The image name to isolate goss testing to.
      --image-version TEXT            The image version to isolate goss testing
                                      to.
      --image-variant TEXT            The image type to isolate goss testing to.
      --image-os TEXT                 The image OS to isolate goss testing to.
      --image-platform TEXT           Filters which image build platform to run
                                      tests for, e.g. 'linux/amd64'. Image test
                                      targets incompatible with the given
                                      platform(s) will be skipped. Requires a
                                      compatible goss binary.  [default: (amd64)]
      --dev-versions [include|exclude|only]
                                      Include or exclude development versions
                                      defined in config.  [default: exclude]
      --dev-channel [release|preview|daily]
                                      Filter development versions to a specific
                                      release channel.
      --dev-spec TEXT                 JSON spec for a dispatched dev build. Ex:
                                      '{"version": "2026.05.0-dev+185-gSHA",
                                      "channel": "daily"}'  [env var:
                                      BAKERY_DEV_SPEC]
      --matrix-versions [include|exclude|only]
                                      Include or exclude versions defined in image
                                      matrix.  [default: exclude]
      --latest                        Run tests only against the latest version of
                                      each image. Development versions are ignored
                                      by this filter.
      --metadata-file PATH            Path to a build metadata file. If given,
                                      attempts to run tests against image
                                      artifacts in the file.
      --clean / --no-clean            Clean up intermediary and temporary files
                                      after building. Can be helpful for
                                      debugging.  [default: clean]
      -v, --verbose                   Enable debug logging
      -q, --quiet                     Supress all output except errors
      --help                          Show this message and exit.

## Options

`--context``:`` ``DIRECTORY`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory where invoked.

`--image-name``:`` ``TEXT`  
The image name to isolate goss testing to.

`--image-version``:`` ``TEXT`  
The image version to isolate goss testing to.

`--image-variant``:`` ``TEXT`  
The image type to isolate goss testing to.

`--image-os``:`` ``TEXT`  
The image OS to isolate goss testing to.

`--image-platform``:`` ``TEXT`  
Filters which image build platform to run tests for, e.g. `linux/amd64`. Image test targets incompatible with the given platform(s) will be skipped. Requires a compatible goss binary.

`--dev-versions``:`` ``CHOICE`` ``=`` ``DevVersionInclusionEnum.EXCLUDE`  
Include or exclude development versions defined in config.

`--dev-channel``:`` ``CHOICE`  
Filter development versions to a specific release channel.

`--dev-spec``:`` ``TEXT`  
JSON spec for a dispatched dev build. Ex: `{"version": "2026.05.0-dev+185-gSHA", "channel": "daily"}` Environment variable: `BAKERY_DEV_SPEC`.

`--matrix-versions``:`` ``CHOICE`` ``=`` ``MatrixVersionInclusionEnum.EXCLUDE`  
Include or exclude versions defined in image matrix.

`--latest`  
Run tests only against the latest version of each image. Development versions are ignored by this filter.

`--metadata-file``:`` ``PATH`  
Path to a build metadata file. If given, attempts to run tests against image artifacts in the file.

`--clean, --no-clean`  
Clean up intermediary and temporary files after building. Can be helpful for debugging.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

Back to top
