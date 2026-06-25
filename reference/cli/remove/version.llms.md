# bakery remove version

# bakery remove version

Removes an existing version from an image in the bakery project

``` bash
bakery remove version [OPTIONS] IMAGE_NAME IMAGE_VERSION
```

Removes the version subpath and all its contents from the specified image in the bakery project and will remove its configuration from the parent image in the bakery.yaml file.

    Usage: bakery remove version [OPTIONS] IMAGE_NAME IMAGE_VERSION

      Removes an existing version from an image in the bakery project

      Removes the version subpath and all its contents from the specified image in
      the bakery project and will remove its configuration from the parent image
      in the bakery.yaml file.

    Arguments:
      IMAGE_NAME     The image to which the version to be removed belongs. This
                     must match an image name present in the bakery.yaml
                     configuration.  [required]
      IMAGE_VERSION  The image version to remove.  [required]

    Options:
      --context DIRECTORY  The root path to use. Defaults to the current working
                           directory where invoked.  [default: (.)]
      -v, --verbose        Enable debug logging
      -q, --quiet          Supress all output except errors
      --help               Show this message and exit.

## Arguments

`IMAGE_NAME``:`` ``TEXT`  
Required.

`IMAGE_VERSION``:`` ``TEXT`  
Required.

## Options

`--context``:`` ``DIRECTORY`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory where invoked.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

Back to top
