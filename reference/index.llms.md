# Reference

## Configuration

Models for bakery.yaml

[config.BakeryConfigDocument](../reference/config.BakeryConfigDocument.llms.md#posit_bakery.config.BakeryConfigDocument)  
Model representation of the top-level bakery.yaml configuration document.

[config.BakeryConfig](../reference/config.BakeryConfig.llms.md#posit_bakery.config.BakeryConfig)  
Manager for the bakery.yaml configuration file and operations against the configuration.

[config.ImageVersionOS](../reference/config.ImageVersionOS.llms.md#posit_bakery.config.ImageVersionOS)  
Model representing a supported operating system for an image version.

[config.ImageVersion](../reference/config.ImageVersion.llms.md#posit_bakery.config.ImageVersion)  
Model representing a version of an image.

[config.ImageVariant](../reference/config.ImageVariant.llms.md#posit_bakery.config.ImageVariant)  
Model representing a variant of an image.

[config.Image](../reference/config.Image.llms.md#posit_bakery.config.Image)  
Model representing an image in the bakery configuration.

[config.BaseRegistry](../reference/config.BaseRegistry.llms.md#posit_bakery.config.BaseRegistry)  
Model representing an image registry in the Bakery configuration.

[config.Registry](../reference/config.Registry.llms.md#posit_bakery.config.Registry)  
Model representing an image from a registry in the Bakery configuration.

[config.Repository](../reference/config.Repository.llms.md#posit_bakery.config.Repository)  
Model representing a project repository in the Bakery configuration.

[config.TagPattern](../reference/config.TagPattern.llms.md#posit_bakery.config.TagPattern)  
Model representing a tag pattern for images in the Bakery configuration.

## Image

Image build targets and plans

[image.BakePlan](../reference/image.BakePlan.llms.md#posit_bakery.image.BakePlan)  
Represents a JSON bake plan for building Docker images using Docker Bake.

[image.ImageTarget](../reference/image.ImageTarget.llms.md#posit_bakery.image.ImageTarget)  
Represents a combination of image variant, image version, and image version OS that make up a target image.

[image.ImageTargetContext](../reference/image.ImageTargetContext.llms.md#posit_bakery.image.ImageTargetContext)  
Container for contextual path information related to an image target.

[image.ImageBuildStrategy](../reference/image.ImageBuildStrategy.llms.md#posit_bakery.image.ImageBuildStrategy)  
Enumeration for image build strategies.

## Plugins

Protocol for extending bakery with custom tools

[plugins.ToolCallResult](../reference/plugins.ToolCallResult.llms.md#posit_bakery.plugins.ToolCallResult)  
Represent the result of a tool call.

[plugins.BakeryToolPlugin](../reference/plugins.BakeryToolPlugin.llms.md#posit_bakery.plugins.BakeryToolPlugin)  

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

[error.BakeryTemplateError](../reference/error.BakeryTemplateError.llms.md#posit_bakery.error.BakeryTemplateError)  
Generic error for template issues

[error.BakeryRenderError](../reference/error.BakeryRenderError.llms.md#posit_bakery.error.BakeryRenderError)  
Generic error for rendering issues

[error.BakeryRenderErrorGroup](../reference/error.BakeryRenderErrorGroup.llms.md#posit_bakery.error.BakeryRenderErrorGroup)  
Group of template errors

[error.BakeryFileError](../reference/error.BakeryFileError.llms.md#posit_bakery.error.BakeryFileError)  
Generic error for file/directory issues

[error.BakeryToolError](../reference/error.BakeryToolError.llms.md#posit_bakery.error.BakeryToolError)  
Generic error for external tool issues

[error.BakeryToolNotFoundError](../reference/error.BakeryToolNotFoundError.llms.md#posit_bakery.error.BakeryToolNotFoundError)  
Error for an expected tool not being found

[error.BakeryToolRuntimeError](../reference/error.BakeryToolRuntimeError.llms.md#posit_bakery.error.BakeryToolRuntimeError)  

[error.BakeryToolRuntimeErrorGroup](../reference/error.BakeryToolRuntimeErrorGroup.llms.md#posit_bakery.error.BakeryToolRuntimeErrorGroup)  
Group of tool runtime errors

[error.BakeryBuildErrorGroup](../reference/error.BakeryBuildErrorGroup.llms.md#posit_bakery.error.BakeryBuildErrorGroup)  
Group of tool runtime errors

[error.BakeryError](../reference/error.BakeryError.llms.md#posit_bakery.error.BakeryError)  
Base class for all Bakery exceptions

Back to top
