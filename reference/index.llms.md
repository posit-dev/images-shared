# API Reference

## Configuration

Models for bakery.yaml

[config](../reference/config.llms.md#posit_bakery.config)  

## Image

Image build targets and plans

[image](../reference/image.llms.md#posit_bakery.image)  

## Plugins

Protocol for extending bakery with custom tools

[plugins](../reference/plugins.llms.md#posit_bakery.plugins)  

## Registry Management

Clients for DockerHub and GHCR

[registry_management.dockerhub.DockerhubClient](../reference/registry_management.dockerhub.DockerhubClient.llms.md#posit_bakery.registry_management.dockerhub.DockerhubClient)  

[registry_management.dockerhub.clean_registry()](../reference/registry_management.dockerhub.clean_registry.llms.md#posit_bakery.registry_management.dockerhub.clean_registry)  
Cleans up images in the specified registry.

[registry_management.dockerhub.push_readmes()](../reference/registry_management.dockerhub.push_readmes.llms.md#posit_bakery.registry_management.dockerhub.push_readmes)  
Push READMEs to Docker Hub for eligible image targets.

[registry_management.ghcr.GHCRClient](../reference/registry_management.ghcr.GHCRClient.llms.md#posit_bakery.registry_management.ghcr.GHCRClient)  

[registry_management.ghcr.clean_registry()](../reference/registry_management.ghcr.clean_registry.llms.md#posit_bakery.registry_management.ghcr.clean_registry)  
Cleans up images in the specified registry.

[registry_management.ghcr.clean_temporary_artifacts()](../reference/registry_management.ghcr.clean_temporary_artifacts.llms.md#posit_bakery.registry_management.ghcr.clean_temporary_artifacts)  
Cleans up temporary caches and images that are not tagged or are older than a given timedelta.

[registry_management.ghcr.GHCRPackageVersion](../reference/registry_management.ghcr.GHCRPackageVersion.llms.md#posit_bakery.registry_management.ghcr.GHCRPackageVersion)  
Represents a GitHub Container Registry package version.

[registry_management.ghcr.GHCRPackageVersionMetadata](../reference/registry_management.ghcr.GHCRPackageVersionMetadata.llms.md#posit_bakery.registry_management.ghcr.GHCRPackageVersionMetadata)  
Represents metadata for a GitHub Container Registry package version.

[registry_management.ghcr.GHCRPackageVersionContainerMetadata](../reference/registry_management.ghcr.GHCRPackageVersionContainerMetadata.llms.md#posit_bakery.registry_management.ghcr.GHCRPackageVersionContainerMetadata)  
Represents container metadata for a GitHub Container Registry package version.

[registry_management.ghcr.GHCRPackageVersions](../reference/registry_management.ghcr.GHCRPackageVersions.llms.md#posit_bakery.registry_management.ghcr.GHCRPackageVersions)  
Represents a list of GitHub Container Registry package versions.

## Errors

Exception hierarchy

[error](../reference/error.llms.md#posit_bakery.error)  

Back to top
