# config.BaseRegistry

# config.BaseRegistry

Model representing an image registry in the Bakery configuration.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/config/registry.py#L8-L32)

``` python
config.BaseRegistry()
```

## Attributes

| Name                          | Description                        |
|-------------------------------|------------------------------------|
| [base_url](#base_url)         | Get the base URL for the registry. |
| [model_config](#model_config) | dict() -\> new empty dictionary    |

### base_url

Get the base URL for the registry.

`base_url``:`` ``str`

### model_config

dict() -\> new empty dictionary

`model_config``=``ConfigDict(extra=``"forbid"``)`  

dict(mapping) -\> new dictionary initialized from a mapping object’s (key, value) pairs dict(iterable) -\> new dictionary initialized as if via: d = {} for k, v in iterable: d\[k\] = v dict(\*\*kwargs) -\> new dictionary initialized with the name=value pairs in the keyword argument list. For example: dict(one=1, two=2)

Back to top
