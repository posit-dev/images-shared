# bakery get tags

# bakery get tags

Get the list of tags that would be built for the given context and filters.

``` bash
bakery get tags [OPTIONS]
```

    Usage: bakery get tags [OPTIONS]

      Get the list of tags that would be built for the given context and filters.

    Options:
      --image-name TEXT               The image name to isolate tags to.
      --image-version TEXT            The image version to isolate tags to.
      --image-variant TEXT            The image variant to isolate tags to.
      --image-os TEXT                 The image OS to isolate tags to.
      --dev-versions [include|exclude|only]
                                      Include development versions defined in
                                      config.  [default: exclude]
      --dev-channel [release|preview|daily]
                                      Filter development versions to a specific
                                      release channel.
      --matrix-versions [include|exclude|only]
                                      Include versions defined in image matrix.
                                      [default: exclude]
      --latest                        Show tags only for the latest version of
                                      each image. Development versions are ignored
                                      by this filter.
      --output [component|uid]        Output format for tags.  [default:
                                      component]
      --context DIRECTORY             The root path to use. Defaults to the
                                      current working directory where invoked.
                                      [default: (.)]
      -v, --verbose                   Enable debug logging
      -q, --quiet                     Supress all output except errors
      --help                          Show this message and exit.

## Options

`--image-name``:`` ``TEXT`  
The image name to isolate tags to.

`--image-version``:`` ``TEXT`  
The image version to isolate tags to.

`--image-variant``:`` ``TEXT`  
The image variant to isolate tags to.

`--image-os``:`` ``TEXT`  
The image OS to isolate tags to.

`--dev-versions``:`` ``CHOICE`` ``=`` ``DevVersionInclusionEnum.EXCLUDE`  
Include development versions defined in config.

`--dev-channel``:`` ``CHOICE`  
Filter development versions to a specific release channel.

`--matrix-versions``:`` ``CHOICE`` ``=`` ``MatrixVersionInclusionEnum.EXCLUDE`  
Include versions defined in image matrix.

`--latest`  
Show tags only for the latest version of each image. Development versions are ignored by this filter.

`--output``:`` ``CHOICE`` ``=`` ``GetTagsOutputFormat.COMPONENT`  
Output format for tags.

`--context``:`` ``DIRECTORY`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory where invoked.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

Back to top
