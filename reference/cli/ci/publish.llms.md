# bakery ci publish

# bakery ci publish

Publish multi-platform images by composing oras index-create → soci-convert → oras index-copy.

``` bash
bakery ci publish [OPTIONS] METADATA_FILE...
```

Which targets are converted is driven by configuration: each target is converted only when its resolved SOCI options have `enabled: true` (set via the `soci` tool options on an image or variant). Targets without SOCI enabled pass through the convert phase untouched. Conversion runs in standalone (no containerd) mode via oras.

Temporary indexes are left in place and cleaned up out-of-band by the clean.yml workflow (bakery clean temp-registry) rather than deleted here.

The orchestration itself lives in the `imagetools` plugin (:meth:`ImageToolsPlugin.publish`); this command is a thin wrapper.

Replaces `bakery ci merge`; the latter is preserved as a thin alias.

    Usage: bakery ci publish [OPTIONS] METADATA_FILE...

      Publish multi-platform images by composing oras index-create → soci-convert
      → oras index-copy.

      Which targets are converted is driven by configuration: each target is
      converted only when its resolved SOCI options have ``enabled: true`` (set
      via the ``soci`` tool options on an image or variant). Targets without SOCI
      enabled pass through the convert phase untouched. Conversion runs in
      standalone (no containerd) mode via oras.

      Temporary indexes are left in place and cleaned up out-of-band by the
      clean.yml workflow (bakery clean temp-registry) rather than deleted here.

      The orchestration itself lives in the ``imagetools`` plugin
      (:meth:`ImageToolsPlugin.publish`); this command is a thin wrapper.

      Replaces `bakery ci merge`; the latter is preserved as a thin alias.

    Arguments:
      METADATA_FILE...  Path to input build metadata JSON file(s).  [required]

    Options:
      --context PATH                  The root path to use. Defaults to the
                                      current working directory.  [default: (.)]
      --image-name TEXT               Filter publish to a specific image name
                                      (regex, e.g. '^workbench$').
      --temp-registry TEXT            Temporary registry to use for split/merge
                                      builds.
      -j, --jobs INTEGER RANGE        Maximum number of targets to publish
                                      concurrently. Defaults to the
                                      BAKERY_MAX_CONCURRENCY env var or a built-in
                                      default.  [x>=1]
      --dry-run / --no-dry-run        If set, no images will be pushed.  [default:
                                      no-dry-run]
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
The root path to use. Defaults to the current working directory.

`--image-name``:`` ``TEXT`  
Filter publish to a specific image name (regex, e.g. `^workbench$`).

`--temp-registry``:`` ``TEXT`  
Temporary registry to use for split/merge builds.

`-j, --jobs``:`` ``INTEGER RANGE`  
Maximum number of targets to publish concurrently. Defaults to the BAKERY_MAX_CONCURRENCY env var or a built-in default.

`--dry-run, --no-dry-run`  
If set, no images will be pushed.

`--dev-channel``:`` ``CHOICE`  
Filter development versions to a specific release channel.

`--dev-spec``:`` ``TEXT`  
JSON spec for a dispatched dev build. Ex: `{"version": "2026.05.0-dev+185-gSHA", "channel": "daily"}` Environment variable: `BAKERY_DEV_SPEC`.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

Back to top
