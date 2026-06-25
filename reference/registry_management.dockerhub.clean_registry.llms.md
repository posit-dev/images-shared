# registry_management.dockerhub.clean_registry()

# registry_management.dockerhub.clean_registry()

Cleans up images in the specified registry.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/registry_management/dockerhub/clean.py#L11-L47)

``` python
registry_management.dockerhub.clean_registry(
    image_registry,
    remove_tagged_older_than=timedelta(weeks=80),
    remove_untagged_older_than=timedelta(weeks=26),
    dry_run=False
)
```

Back to top
