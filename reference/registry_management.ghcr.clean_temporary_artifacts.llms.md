# registry_management.ghcr.clean_temporary_artifacts()

# registry_management.ghcr.clean_temporary_artifacts()

Cleans up temporary caches and images that are not tagged or are older than a given timedelta.

Usage

[Source](https://github.com/posit-dev/images-shared/blob/main/posit_bakery/registry_management/ghcr/clean.py#L15-L61)

``` python
registry_management.ghcr.clean_temporary_artifacts(
    ghcr_registry, remove_untagged=True, remove_older_than=None, dry_run=False
)
```

Back to top
