# bakery ci matrix

# bakery ci matrix

Generates a JSON matrix of image versions for CI workflows to consume

``` bash
bakery ci matrix [OPTIONS] [IMAGE_NAME]
```

The output is a JSON array of objects with the following structure:

``` json
[
  {
    "image": "image-name",
    "version": "version-name",
    "dev": false,
    "platform": "linux/amd64"
  }
]
```

    Usage: bakery ci matrix [OPTIONS] [IMAGE_NAME]

      Generates a JSON matrix of image versions for CI workflows to consume

      The output is a JSON array of objects with the following structure:

      ```json
      [
        {
          "image": "image-name",
          "version": "version-name",
          "dev": false,
          "platform": "linux/amd64"
        }
      ]

Arguments: \[IMAGE_NAME\] The image name to isolate matrix to.

Options: –dev-versions \[include\|exclude\|only\] Include or exclude development versions defined in config. \[default: exclude\] –dev-channel \[release\|preview\|daily\] Filter development versions to a specific release channel. –matrix-versions \[include\|exclude\|only\] Include or exclude versions defined in image matrix. \[default: exclude\] –image-version TEXT The image version to filter to. –exclude \[version\|dev\|platform\] Fields to exclude splitting the matrix by. –context DIRECTORY The root path to use. Defaults to the current working directory where invoked. \[default: (.)\] –dev-spec TEXT JSON spec for a dispatched dev build. Ex: ‘{“version”: “2026.05.0-dev+185-gSHA”, “channel”: “daily”}’ \[env var: BAKERY_DEV_SPEC\] -v, –verbose Enable debug logging -q, –quiet Supress all output except errors –help Show this message and exit. \`\`\`

## Arguments

`IMAGE_NAME``:`` ``TEXT`  
Optional.

## Options

`--dev-versions``:`` ``CHOICE`` ``=`` ``DevVersionInclusionEnum.EXCLUDE`  
Include or exclude development versions defined in config.

`--dev-channel``:`` ``CHOICE`  
Filter development versions to a specific release channel.

`--matrix-versions``:`` ``CHOICE`` ``=`` ``MatrixVersionInclusionEnum.EXCLUDE`  
Include or exclude versions defined in image matrix.

`--image-version``:`` ``TEXT`  
The image version to filter to.

`--exclude``:`` ``CHOICE`  
Fields to exclude splitting the matrix by.

`--context``:`` ``DIRECTORY`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory where invoked.

`--dev-spec``:`` ``TEXT`  
JSON spec for a dispatched dev build. Ex: `{"version": "2026.05.0-dev+185-gSHA", "channel": "daily"}` Environment variable: `BAKERY_DEV_SPEC`.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

Back to top
