# bakery imagetools merge

# bakery imagetools merge

Merge multi-platform images from build metadata files using ORAS.

``` bash
bakery imagetools merge [OPTIONS] METADATA_FILE...
```

Takes one or more build metadata JSON files (produced by `bakery build --strategy build`) and merges platform-specific images into multi-platform manifest indexes.

    Usage: bakery imagetools merge [OPTIONS] METADATA_FILE...

      Merge multi-platform images from build metadata files using ORAS.

      Takes one or more build metadata JSON files (produced by `bakery build --strategy build`)
      and merges platform-specific images into multi-platform manifest indexes.

    Arguments:
      METADATA_FILE...  Path to input build metadata JSON file(s) to merge.
                        [required]

    Options:
      --context PATH            The root path to use. Defaults to the current
                                working directory where invoked.  [default: (.)]
      --temp-registry TEXT      Temporary registry to use for multiplatform
                                split/merge builds.
      --dry-run / --no-dry-run  If set, the merged images will not be pushed to
                                the registry.  [default: no-dry-run]
      -v, --verbose             Enable debug logging
      -q, --quiet               Supress all output except errors
      --help                    Show this message and exit.

## Arguments

`METADATA_FILE``:`` ``PATH`  
Required.

## Options

`--context``:`` ``PATH`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory where invoked.

`--temp-registry``:`` ``TEXT`  
Temporary registry to use for multiplatform split/merge builds.

`--dry-run, --no-dry-run`  
If set, the merged images will not be pushed to the registry.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

Back to top
