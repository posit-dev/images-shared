# bakery hadolint run

# bakery hadolint run

Runs hadolint against Containerfiles in the context path

``` bash
bakery hadolint run [OPTIONS]
```

If no options are provided, the command lints all image Containerfiles in the project and writes results to the `results/hadolint/` directory in the context path.

Requires hadolint to be installed on the system. The path to the binary can be set with the `HADOLINT_PATH` environment variable if not present in the system PATH.

    Usage: bakery hadolint run [OPTIONS]

      Runs hadolint against Containerfiles in the context path

      If no options are provided, the command lints all image Containerfiles in the project and writes
      results to the `results/hadolint/` directory in the context path.

      Requires hadolint to be installed on the system. The path to the binary can be set with the
      `HADOLINT_PATH` environment variable if not present in the system PATH.

    Options:
      --context DIRECTORY             The root path to use. Defaults to the
                                      current working directory.  [default: (.)]
      --image-name TEXT               The image name to isolate linting to.
      --image-version TEXT            The image version to isolate linting to.
      --image-variant TEXT            The image variant to isolate linting to.
      --image-os TEXT                 The image OS to isolate linting to.
      --dev-versions [include|exclude|only]
                                      Include or exclude development versions
                                      defined in config.  [default: exclude]
      --matrix-versions [include|exclude|only]
                                      Include or exclude versions defined in image
                                      matrix.  [default: exclude]
      --latest                        Lint only the latest version of each image.
                                      Development versions are ignored by this
                                      filter.
      --failure-threshold TEXT        Exit with failure if any rule at or above
                                      this severity is violated. One of: error,
                                      warning, info, style, ignore, none.
                                      [default: error]
      --ignore TEXT                   Rule code to ignore (can be repeated).
      --require-label TEXT            Label to require in format 'name:type' (can
                                      be repeated).
      --no-fail                       Always exit with status 0, even when rule
                                      violations are found.
      --error TEXT                    Rule code to treat as error (can be
                                      repeated).
      --warning TEXT                  Rule code to treat as warning (can be
                                      repeated).
      --info TEXT                     Rule code to treat as info (can be
                                      repeated).
      --style TEXT                    Rule code to treat as style (can be
                                      repeated).
      --strict-labels                 Require labels to match the label schema.
      --disable-ignore-pragma         Disable inline hadolint ignore comments.
      --trusted-registry TEXT         Trusted Docker registry (can be repeated).
      -v, --verbose                   Enable debug logging
      -q, --quiet                     Supress all output except errors
      --help                          Show this message and exit.

## Options

`--context``:`` ``DIRECTORY`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory.

`--image-name``:`` ``TEXT`  
The image name to isolate linting to.

`--image-version``:`` ``TEXT`  
The image version to isolate linting to.

`--image-variant``:`` ``TEXT`  
The image variant to isolate linting to.

`--image-os``:`` ``TEXT`  
The image OS to isolate linting to.

`--dev-versions``:`` ``CHOICE`` ``=`` ``DevVersionInclusionEnum.EXCLUDE`  
Include or exclude development versions defined in config.

`--matrix-versions``:`` ``CHOICE`` ``=`` ``MatrixVersionInclusionEnum.EXCLUDE`  
Include or exclude versions defined in image matrix.

`--latest`  
Lint only the latest version of each image. Development versions are ignored by this filter.

`--failure-threshold``:`` ``TEXT`  
Exit with failure if any rule at or above this severity is violated. One of: error, warning, info, style, ignore, none. \[default: error\]

`--ignore``:`` ``TEXT`  
Rule code to ignore (can be repeated).

`--require-label``:`` ``TEXT`  
Label to require in format `name:type` (can be repeated).

`--no-fail`  
Always exit with status 0, even when rule violations are found.

`--error``:`` ``TEXT`  
Rule code to treat as error (can be repeated).

`--warning``:`` ``TEXT`  
Rule code to treat as warning (can be repeated).

`--info``:`` ``TEXT`  
Rule code to treat as info (can be repeated).

`--style``:`` ``TEXT`  
Rule code to treat as style (can be repeated).

`--strict-labels`  
Require labels to match the label schema.

`--disable-ignore-pragma`  
Disable inline hadolint ignore comments.

`--trusted-registry``:`` ``TEXT`  
Trusted Docker registry (can be repeated).

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

Back to top
