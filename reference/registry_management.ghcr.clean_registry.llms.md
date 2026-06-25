# registry_management.ghcr.clean_registry()

# registry_management.ghcr.clean_registry()

Cleans up images in the specified registry.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/registry_management/ghcr/clean.py#L64-L109)

``` python
registry_management.ghcr.clean_registry(
    image_registry,
    remove_tagged_older_than=timedelta(weeks=80),
    remove_untagged_older_than=timedelta(weeks=26),
    dry_run=False
)
```

Back to top
