# bakery update version

# bakery update version

Update an existing image version with a new version number.

``` bash
bakery update version [OPTIONS] IMAGE_NAME NEW_VERSION
```

Patches the target version with the new version name. If `--target-version` is not specified, the version marked as latest is used. All existing configuration (dependencies, OS, latest flag) is preserved.

    Usage: bakery update version [OPTIONS] IMAGE_NAME NEW_VERSION

      Update an existing image version with a new version number.

      Patches the target version with the new version name. If --target-version is not
      specified, the version marked as latest is used. All existing configuration
      (dependencies, OS, latest flag) is preserved.

      Examples:
        bakery update version connect 2026.03.1
        # Patches the latest version to '2026.03.1'

        bakery update version connect 2026.03.1 --target-version 2026.03.0   #
        Explicitly patches '2026.03.0' to '2026.03.1'

    Arguments:
      IMAGE_NAME   The image name to update.  [required]
      NEW_VERSION  The new image version name.  [required]

    Options:
      --target-version TEXT  The existing version name to patch. If not specified,
                             the latest version is used.
      --context PATH         The root path to use. Defaults to the current working
                             directory where invoked.  [default: (.)]
      --value TEXT           A 'key=value' pair to pass to the templates. Accepts
                             multiple pairs.
      --clean / --no-clean   Remove all existing version files before rendering
                             from templates.  [default: clean]
      -v, --verbose          Enable debug logging
      -q, --quiet            Supress all output except errors
      --help                 Show this message and exit.

## Arguments

`IMAGE_NAME``:`` ``TEXT`  
Required.

`NEW_VERSION``:`` ``TEXT`  
Required.

## Options

`--target-version``:`` ``TEXT`  
The existing version name to patch. If not specified, the latest version is used.

`--context``:`` ``PATH`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory where invoked.

`--value``:`` ``TEXT`  
A `key=value` pair to pass to the templates. Accepts multiple pairs.

`--clean, --no-clean`  
Remove all existing version files before rendering from templates.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

## Examples

``` bash
bakery update version connect 2026.03.1
# Patches the latest version to '2026.03.1'

bakery update version connect 2026.03.1 --target-version 2026.03.0
# Explicitly patches '2026.03.0' to '2026.03.1'
```

Back to top
