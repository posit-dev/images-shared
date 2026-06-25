# bakery wizcli scan

# bakery wizcli scan

Scan container images for vulnerabilities using WizCLI.

``` bash
bakery wizcli scan [OPTIONS]
```

Runs `wizcli scan container-image` against each image target in the project. Results are written as JSON files to the `results/wizcli/` directory.

Images are expected to be available to the local Docker daemon. It is advised to run `build` before running wizcli scans.

Requires wizcli to be installed on the system. The path to the binary can be set with the `WIZCLI_PATH` environment variable if not present in the system PATH. Authentication can be provided via `--client-id`/`--client-secret` options or the `WIZ_CLIENT_ID`/`WIZ_CLIENT_SECRET` environment variables.

    Usage: bakery wizcli scan [OPTIONS]

      Scan container images for vulnerabilities using WizCLI.

      Runs `wizcli scan container-image` against each image target in the project.
      Results are written as JSON files to the `results/wizcli/` directory.

      Images are expected to be available to the local Docker daemon. It is advised
      to run `build` before running wizcli scans.

      Requires wizcli to be installed on the system. The path to the binary can be
      set with the `WIZCLI_PATH` environment variable if not present in the system PATH.
      Authentication can be provided via `--client-id`/`--client-secret` options or
      the `WIZ_CLIENT_ID`/`WIZ_CLIENT_SECRET` environment variables.

    Options:
      --context DIRECTORY             The root path to use. Defaults to the
                                      current working directory where invoked.
                                      [default: (.)]
      --image-name TEXT               The image name to isolate scanning to.
      --image-version TEXT            The image version to isolate scanning to.
      --image-variant TEXT            The image variant to isolate scanning to.
      --image-os TEXT                 The image OS to isolate scanning to.
      --image-platform TEXT           Filters which image build platform to scan.
                                      [default: (amd64)]
      --dev-versions [include|exclude|only]
                                      Include or exclude development versions
                                      defined in config.  [default: exclude]
      --matrix-versions [include|exclude|only]
                                      Include or exclude versions defined in image
                                      matrix.  [default: exclude]
      --latest                        Scan only the latest version of each image.
                                      Development versions are ignored by this
                                      filter.
      --metadata-file PATH            Path to a build metadata file. If given,
                                      attempts to scan image artifacts in the
                                      file.
      --disabled-scanners TEXT        Comma-separated scanners to disable (e.g.
                                      Vulnerability,Secret,Malware).
      --driver TEXT                   Driver used to scan image (extract, mount,
                                      mountWithLayers).
      --timeout TEXT                  Timeout for the scan (e.g. 1h, 30m).
      --no-publish                    Disable publishing scan results to the Wiz
                                      portal.
      --scan-context-id TEXT          Context identifier that defines scan
                                      granularity.
      --log TEXT                      File path for wizcli debug logs.
      --client-id TEXT                Wiz service account client ID (overrides
                                      WIZ_CLIENT_ID env var).
      --client-secret TEXT            Wiz service account client secret (overrides
                                      WIZ_CLIENT_SECRET env var).
      --use-device-code               Use device code flow for authentication.
      --no-browser                    Do not open browser for device code flow.
      -v, --verbose                   Enable debug logging
      -q, --quiet                     Supress all output except errors
      --help                          Show this message and exit.

## Options

`--context``:`` ``DIRECTORY`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory where invoked.

`--image-name``:`` ``TEXT`  
The image name to isolate scanning to.

`--image-version``:`` ``TEXT`  
The image version to isolate scanning to.

`--image-variant``:`` ``TEXT`  
The image variant to isolate scanning to.

`--image-os``:`` ``TEXT`  
The image OS to isolate scanning to.

`--image-platform``:`` ``TEXT`  
Filters which image build platform to scan.

`--dev-versions``:`` ``CHOICE`` ``=`` ``DevVersionInclusionEnum.EXCLUDE`  
Include or exclude development versions defined in config.

`--matrix-versions``:`` ``CHOICE`` ``=`` ``MatrixVersionInclusionEnum.EXCLUDE`  
Include or exclude versions defined in image matrix.

`--latest`  
Scan only the latest version of each image. Development versions are ignored by this filter.

`--metadata-file``:`` ``PATH`  
Path to a build metadata file. If given, attempts to scan image artifacts in the file.

`--disabled-scanners``:`` ``TEXT`  
Comma-separated scanners to disable (e.g. Vulnerability,Secret,Malware).

`--driver``:`` ``TEXT`  
Driver used to scan image (extract, mount, mountWithLayers).

`--timeout``:`` ``TEXT`  
Timeout for the scan (e.g. 1h, 30m).

`--no-publish`  
Disable publishing scan results to the Wiz portal.

`--scan-context-id``:`` ``TEXT`  
Context identifier that defines scan granularity.

`--log``:`` ``TEXT`  
File path for wizcli debug logs.

`--client-id``:`` ``TEXT`  
Wiz service account client ID (overrides WIZ_CLIENT_ID env var).

`--client-secret``:`` ``TEXT`  
Wiz service account client secret (overrides WIZ_CLIENT_SECRET env var).

`--use-device-code`  
Use device code flow for authentication.

`--no-browser`  
Do not open browser for device code flow.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

Back to top
