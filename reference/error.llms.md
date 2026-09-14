# error

`error`

Usage

## Classes

| Name | Description |
|----|----|
| [BakeryBuildErrorGroup](#BakeryBuildErrorGroup) | Group of tool runtime errors |
| [BakeryError](#BakeryError) | Base class for all Bakery exceptions |
| [BakeryFileError](#BakeryFileError) | Generic error for file/directory issues |
| [BakeryRenderError](#BakeryRenderError) | Generic error for rendering issues |
| [BakeryRenderErrorGroup](#BakeryRenderErrorGroup) | Group of template errors |
| [BakeryTemplateError](#BakeryTemplateError) | Generic error for template issues |
| [BakeryToolError](#BakeryToolError) | Generic error for external tool issues |
| [BakeryToolNotFoundError](#BakeryToolNotFoundError) | Error for an expected tool not being found |
| [BakeryToolRuntimeErrorGroup](#BakeryToolRuntimeErrorGroup) | Group of tool runtime errors |

### BakeryBuildErrorGroup

Group of tool runtime errors

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/error.py#L168-L185)

``` python
BakeryBuildErrorGroup()
```

### BakeryError

Base class for all Bakery exceptions

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/error.py#L8-L11)

``` python
BakeryError()
```

### BakeryFileError

Generic error for file/directory issues

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/error.py#L73-L92)

``` python
BakeryFileError(message=None, filepath=None)
```

### BakeryRenderError

Generic error for rendering issues

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/error.py#L20-L57)

``` python
BakeryRenderError(
    cause,
    context=None,
    image=None,
    version=None,
    variant=None,
    template=None,
    destination=None
)
```

### BakeryRenderErrorGroup

Group of template errors

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/error.py#L60-L70)

``` python
BakeryRenderErrorGroup()
```

### BakeryTemplateError

Generic error for template issues

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/error.py#L14-L17)

``` python
BakeryTemplateError()
```

### BakeryToolError

Generic error for external tool issues

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/error.py#L95-L101)

``` python
BakeryToolError(message=None, tool_name=None)
```

### BakeryToolNotFoundError

Error for an expected tool not being found

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/error.py#L104-L107)

``` python
BakeryToolNotFoundError(message=None, tool_name=None)
```

### BakeryToolRuntimeErrorGroup

Group of tool runtime errors

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/error.py#L155-L165)

``` python
BakeryToolRuntimeErrorGroup()
```

Back to top
