# bakery imagetools soci-convert

# bakery imagetools soci-convert

Convert images referenced by build-metadata JSON files into SOCI-enabled images.

``` bash
bakery imagetools soci-convert [OPTIONS] METADATA_FILE...
```

Conversion runs in standalone (no-containerd) mode via oras. Targets without `tool: soci, enabled: true` in bakery.yaml are skipped.

    Usage: bakery imagetools soci-convert [OPTIONS] METADATA_FILE...

      Convert images referenced by build-metadata JSON files into SOCI-enabled
      images.

      Conversion runs in standalone (no-containerd) mode via oras. Targets
      without `tool: soci, enabled: true` in bakery.yaml are skipped.

    Arguments:
      METADATA_FILE...  Path to input build metadata JSON file(s).  [required]

    Options:
      --context PATH            The root path to use. Defaults to the current
                                working directory.  [default: (.)]
      --temp-registry TEXT      Temporary registry to use for split/merge builds.
      --dry-run / --no-dry-run  Log commands without executing them.  [default:
                                no-dry-run]
      -v, --verbose             Enable debug logging
      -q, --quiet               Supress all output except errors
      --help                    Show this message and exit.

## Arguments

`METADATA_FILE``:`` ``PATH`  
Required.

## Options

`--context``:`` ``PATH`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory.

`--temp-registry``:`` ``TEXT`  
Temporary registry to use for split/merge builds.

`--dry-run, --no-dry-run`  
Log commands without executing them.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

Back to top
