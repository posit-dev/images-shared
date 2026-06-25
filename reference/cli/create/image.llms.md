# bakery create image

# bakery create image

Creates a quickstart skeleton for a new image in the context path

``` bash
bakery create image [OPTIONS] IMAGE_NAME
```

This tool will create a new directory in the context path with the following structure:

    .
    └── image_name/
        └── template/
            ├── deps/
            │   └── packages.txt.jinja2
            ├── test/
            │   └── goss.yaml.jinja2
            └── Containerfile.jinja2

    Usage: bakery create image [OPTIONS] IMAGE_NAME

      Creates a quickstart skeleton for a new image in the context path

      This tool will create a new directory in the context path with the following
      structure:

. └── image_name/ └── template/ ├── deps/ │ └── packages.txt.jinja2 ├── test/ │ └── goss.yaml.jinja2 └── Containerfile.jinja2 \`\`\`

Arguments: IMAGE_NAME The image name to create a skeleton for. \[required\]

Options: –context DIRECTORY The root path to use. Defaults to the current working directory where invoked. \[default: (.)\] –base-image TEXT The base to use for the new image. \[default: docker.io/library/ubuntu:22.04\] –subpath TEXT The directory name to use for the image. \[default: (based on image_name)\] –display-name TEXT The display name for the image. \[default: (based on image_name)\] –description TEXT The description for the image. Used in labels. –documentation-url TEXT The documentation URL for the image. -v, –verbose Enable debug logging -q, –quiet Supress all output except errors –help Show this message and exit. \`\`\`

## Arguments

`IMAGE_NAME``:`` ``TEXT`  
Required.

## Options

`--context``:`` ``DIRECTORY`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory where invoked.

`--base-image``:`` ``TEXT`` ``=`` ``docker.io/library/ubuntu:22.04`  
The base to use for the new image.

`--subpath``:`` ``TEXT`  
The directory name to use for the image.

`--display-name``:`` ``TEXT`  
The display name for the image.

`--description``:`` ``TEXT`  
The description for the image. Used in labels.

`--documentation-url``:`` ``TEXT`  
The documentation URL for the image.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

Back to top
