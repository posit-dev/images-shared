# bakery create project

# bakery create project

Creates a new project in the context path

``` bash
bakery create project [OPTIONS]
```

This tool will create a new directory in the context path with the following structure:

    .
    └── context/
        └── bakery.yaml.

    Usage: bakery create project [OPTIONS]

      Creates a new project in the context path

      This tool will create a new directory in the context path with the following
      structure:

. └── context/ └── bakery.yaml. \`\`\`

Options: –context DIRECTORY The root path to use. Defaults to the current working directory where invoked. \[default: (.)\] -v, –verbose Enable debug logging -q, –quiet Supress all output except errors –help Show this message and exit. \`\`\`

## Options

`--context``:`` ``DIRECTORY`` ``=`` ``/home/runner/work/images-shared/images-shared/posit-bakery/great-docs`  
The root path to use. Defaults to the current working directory where invoked.

`-v, --verbose`  
Enable debug logging

`-q, --quiet`  
Supress all output except errors

Back to top
