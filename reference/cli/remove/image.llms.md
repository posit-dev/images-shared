# bakery remove image

# bakery remove image

Removes an existing image from the bakery project

``` bash
bakery remove image [OPTIONS] IMAGE_NAME
```

Removes the image directory and all its contents from the bakery project and will remove its configuration from the bakery.yaml file.

    Usage: bakery remove image [OPTIONS] IMAGE_NAME

      Removes an existing image from the bakery project

      Removes the image directory and all its contents from the bakery project and
      will remove its configuration from the bakery.yaml file.

    Arguments:
      IMAGE_NAME  The image name to remove files and configurations for.
                  [required]

    Options:
      --context DIRECTORY  The root path to use. Defaults to the current working
                           directory where invoked.  [default: (.)]
      -v, --verbose        Enable debug logging
      -q, --quiet          Supress all output except errors
      --help               Show this message and exit.

## Arguments

`IMAGE_NAME``:`` ``TEXT`  
Required.

## Options

`--context``:`` ``DIRECTORY`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory where invoked.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

Back to top
