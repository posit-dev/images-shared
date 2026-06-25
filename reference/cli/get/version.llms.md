# bakery get version

# bakery get version

Get a version name from bakery.yaml.

``` bash
bakery get version [OPTIONS] IMAGE_NAME
```

Returns the latest version by default. Use `--subpath` to find a version by its configured subpath instead.

    Usage: bakery get version [OPTIONS] IMAGE_NAME

      Get a version name from bakery.yaml.

      Returns the latest version by default. Use --subpath to find a version by its
      configured subpath instead.

      Examples:
        bakery get version connect                    Find the latest version
        bakery get version connect --subpath 2026.03  Find version with subpath '2026.03'

    Arguments:
      IMAGE_NAME  The image name to query.  [required]

    Options:
      --subpath TEXT       Find the version with this subpath.
      --context DIRECTORY  The root path to use. Defaults to the current working
                           directory where invoked.  [default: (.)]
      -v, --verbose        Enable debug logging
      -q, --quiet          Supress all output except errors
      --help               Show this message and exit.

## Arguments

`IMAGE_NAME``:`` ``TEXT`  
Required.

## Options

`--subpath``:`` ``TEXT`  
Find the version with this subpath.

`--context``:`` ``DIRECTORY`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory where invoked.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

## Examples

``` bash
bakery get version connect                    Find the latest version
bakery get version connect --subpath 2026.03  Find version with subpath '2026.03'
```

Back to top
