# plugins.BakeryToolPlugin

# plugins.BakeryToolPlugin

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/plugins/protocol.py#L24-L44)

``` python
plugins.BakeryToolPlugin()
```

## Methods

| Name | Description |
|----|----|
| [execute()](#execute) | Execute the plugin’s tools against the given ImageTarget objects. |
| [register_cli()](#register_cli) | Register the plugin’s CLI commands with the given Typer app. |
| [results()](#results) | Display the results of the plugin’s execution and exit non-zero on failures. |

### execute()

Execute the plugin’s tools against the given ImageTarget objects.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/plugins/protocol.py#L33-L40)

``` python
execute(base_path, targets, **kwargs)
```

### register_cli()

Register the plugin’s CLI commands with the given Typer app.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/plugins/protocol.py#L29-L31)

``` python
register_cli(app)
```

### results()

Display the results of the plugin’s execution and exit non-zero on failures.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/plugins/protocol.py#L42-L44)

``` python
results(results)
```

Back to top
