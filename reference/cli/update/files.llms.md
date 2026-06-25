# bakery update files

# bakery update files

Renders templates to version files matching the given filters

``` bash
bakery update files [OPTIONS]
```

This command will rerender each matching image version’s files from the templates in the image’s template directory. Existing configuration details for the version such as dependencies, variants, and the latest flag are used and remain unmodified.

Existing files will not be removed, but may be overwritten during template rendering.

    Usage: bakery update files [OPTIONS]

      Renders templates to version files matching the given filters

      This command will rerender each matching image version's files from the templates in the image's template
      directory. Existing configuration details for the version such as dependencies, variants, and the latest flag
      are used and remain unmodified.

      Existing files will not be removed, but may be overwritten during template rendering.

    Options:
      --context DIRECTORY      The root path to use. Defaults to the current
                               working directory where invoked.  [default: (.)]
      --image-name TEXT        The image name to isolate file rendering to.
      --image-version TEXT     The image version to isolate file rendering to.
      --template-pattern TEXT  Regex pattern(s) to filter which templates to
                               render.
      -v, --verbose            Enable debug logging
      -q, --quiet              Supress all output except errors
      --help                   Show this message and exit.

## Options

`--context``:`` ``DIRECTORY`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory where invoked.

`--image-name``:`` ``TEXT`  
The image name to isolate file rendering to.

`--image-version``:`` ``TEXT`  
The image version to isolate file rendering to.

`--template-pattern``:`` ``TEXT`  
Regex pattern(s) to filter which templates to render.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

Back to top
