# bakery ci merge

# bakery ci merge

Alias for `bakery ci publish`.

``` bash
bakery ci merge [OPTIONS] METADATA_FILE...
```

Preserved for back-compat. New callers should prefer `bakery ci publish`. SOCI conversion is driven by per-image/variant `soci` options.

    Usage: bakery ci merge [OPTIONS] METADATA_FILE...

      Alias for `bakery ci publish`.

      Preserved for back-compat. New callers should prefer `bakery ci publish`.
      SOCI conversion is driven by per-image/variant `soci` options.

    Arguments:
      METADATA_FILE...  Path to input build metadata JSON file(s) to merge.
                        [required]

    Options:
      --context PATH                  The root path to use. Defaults to the
                                      current working directory where invoked.
                                      [default: (.)]
      --image-name TEXT               Filter merge to a specific image name
                                      (regex, e.g. '^workbench$').
      --temp-registry TEXT            Temporary registry to use for multiplatform
                                      split/merge builds.
      --dry-run / --no-dry-run        If set, the merged images will not be pushed
                                      to the registry.  [default: no-dry-run]
      --dev-channel [release|preview|daily]
                                      Filter development versions to a specific
                                      release channel.
      --dev-spec TEXT                 JSON spec for a dispatched dev build. Ex:
                                      '{"version": "2026.05.0-dev+185-gSHA",
                                      "channel": "daily"}'  [env var:
                                      BAKERY_DEV_SPEC]
      -v, --verbose                   Enable debug logging
      -q, --quiet                     Supress all output except errors
      --help                          Show this message and exit.

## Arguments

`METADATA_FILE``:`` ``PATH`  
Required.

## Options

`--context``:`` ``PATH`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory where invoked.

`--image-name``:`` ``TEXT`  
Filter merge to a specific image name (regex, e.g. `^workbench$`).

`--temp-registry``:`` ``TEXT`  
Temporary registry to use for multiplatform split/merge builds.

`--dry-run, --no-dry-run`  
If set, the merged images will not be pushed to the registry.

`--dev-channel``:`` ``CHOICE`  
Filter development versions to a specific release channel.

`--dev-spec``:`` ``TEXT`  
JSON spec for a dispatched dev build. Ex: `{"version": "2026.05.0-dev+185-gSHA", "channel": "daily"}` Environment variable: `BAKERY_DEV_SPEC`.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

Back to top
