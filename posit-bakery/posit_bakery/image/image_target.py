import contextlib
import logging
import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated

import python_on_whales
from pydantic import BaseModel, computed_field, ConfigDict, Field
from python_on_whales.components.buildx.imagetools.models import Manifest

from posit_bakery.config.image import ImageVersion, ImageVariant, ImageVersionOS
from posit_bakery.config.repository import Repository
from posit_bakery.config.tag import TagPattern, TagPatternFilter
from posit_bakery.const import OCI_LABEL_PREFIX, POSIT_LABEL_PREFIX, REGEX_IMAGE_TAG_SUFFIX_ALLOWED_CHARACTERS_PATTERN
from posit_bakery.error import BakeryToolRuntimeError, BakeryFileError
from posit_bakery.image.image_metadata import MetadataFile
from posit_bakery.image.util import inspect_image
from posit_bakery.services import RegistryContainer
from posit_bakery.settings import SETTINGS

log = logging.getLogger(__name__)


class ImageBuildStrategy(str, Enum):
    """Enumeration for image build strategies."""

    BUILD = "build"  # Build using sequential build calls to builder
    BAKE = "bake"  # Build using Docker BuildKit bake


class ImageTargetContext(BaseModel):
    """Container for contextual path information related to an image target."""

    model_config = ConfigDict(frozen=True)

    base_path: Path  # Path to the root of the Bakery project
    image_path: Path  # Path to the image directory
    version_path: Path  # Path to the image version directory


class ImageTargetSettings(BaseModel):
    temp_registry: Annotated[
        str | None,
        Field(default=None, description="Temporary registry to use for multiplatform split/merge builds."),
    ]
    cache_registry: Annotated[
        str | None,
        Field(default=None, description="Registry to use for build cache storage and retrieval."),
    ]


class ImageTarget(BaseModel):
    """Represents a combination of image variant, image version, and image version OS that make up a target image.

    Image targets represent a unique image specified by configuration elements. Image targets are the functional
    representation of a bakery.yaml configuration and can be used for various operations such as:
    - Build
    - Push
    - Bake
    - Goss Test
    """

    context: Annotated[ImageTargetContext, Field(description="Contextual path information for the image target.")]
    repository: Annotated[Repository, Field(description="Parent repository of the image target.")]
    image_version: Annotated[ImageVersion, Field(description="ImageVersion of the image target.")]
    image_variant: Annotated[ImageVariant | None, Field(default=None, description="ImageVariant of the image target.")]
    image_os: Annotated[ImageVersionOS | None, Field(default=None, description="ImageVersionOS of the image target.")]
    metadata_file: Annotated[
        MetadataFile | None, Field(default=None, description="Build metadata for the image target.")
    ]
    settings: Annotated[ImageTargetSettings, Field(default_factory=ImageTargetSettings)]

    @classmethod
    def new_image_target(
        cls,
        repository: Repository,
        image_version: ImageVersion,
        image_variant: ImageVariant | None = None,
        image_os: ImageVersionOS | None = None,
        settings: ImageTargetSettings | None = None,
    ) -> "ImageTarget":
        """Create a new ImageTarget instance from a repository, version, variant, and OS combination.

        :param repository: The repository containing the image.
        :param image_version: The specific version of the image.
        :param image_variant: The variant of the image, if applicable.
        :param image_os: The operating system of the image, if applicable.
        :param settings: Optional settings for the image target.

        :return: A new ImageTarget representing the given combination of configurations.
        """
        context = ImageTargetContext(
            base_path=image_version.parent.parent.path,
            image_path=image_version.parent.path,
            version_path=image_version.path,
        )

        return cls(
            context=context,
            repository=repository,
            image_version=image_version,
            image_variant=image_variant,
            image_os=image_os,
            settings=settings or ImageTargetSettings(),
        )

    def __str__(self):
        """Return a string representation of the image target."""
        s = f"ImageTarget(image='{self.image_name}', version='{self.image_version.name}'"
        if self.image_variant:
            s += f", variant='{self.image_variant.name}'"
        if self.image_os:
            s += f", os='{self.image_os.name}'"
        s += ")"
        return s

    @computed_field
    @property
    def uid(self) -> str:
        """Generate a unique identifier for the target based on its properties."""
        u = f"{self.image_name}-{self.image_version.name}"
        if self.image_variant:
            u += f"-{self.image_variant.name}"
        if self.image_os:
            u += f"-{self.image_os.name}"
        return re.sub("[ .+/]", "-", u).lower()

    @property
    def image_name(self) -> str:
        """Return the name of the image."""
        return self.image_version.parent.name

    @property
    def is_latest(self) -> bool:
        """Check if the image version is marked as latest."""
        return self.image_version.latest

    @property
    def is_primary_os(self) -> bool:
        """Check if the image OS is marked as primary."""
        # If no OS is specified, consider it primary by default.
        if self.image_os is None:
            return True
        return self.image_os.primary

    @property
    def is_primary_variant(self) -> bool:
        """Check if the image variant is marked as primary."""
        # If no variant is specified, consider it primary by default.
        if self.image_variant is None:
            return True
        return self.image_variant.primary

    @computed_field
    @property
    def containerfile(self) -> Path:
        """Return the path of the Containerfile for this image target."""
        if not self.context.version_path:
            raise ValueError("Version path is not set in the context.")
        containerfile_name = "Containerfile"
        if self.image_os is not None and self.image_os.extension:
            containerfile_name += f".{self.image_os.extension}"
        if self.image_variant is not None and self.image_variant.extension:
            containerfile_name += f".{self.image_variant.extension}"

        expected_path = self.context.version_path / containerfile_name

        if expected_path.is_absolute():
            expected_path = expected_path.relative_to(self.context.base_path)

        return expected_path

    @property
    def tag_template_values(self) -> dict[str, str]:
        """Return a dictionary of values for templating tags."""
        return {
            "Version": self.image_version.name,
            "Variant": self.image_variant.tagDisplayName if self.image_variant else "",
            "OS": self.image_os.tagDisplayName if self.image_os else "",
            "Name": self.image_name,
        }

    @property
    def tag_patterns(self) -> list[TagPattern]:
        """Ensure tag patterns are unique."""
        patterns = self.image_version.parent.tagPatterns.copy()
        if self.image_variant:
            patterns.extend(self.image_variant.tagPatterns)
        unique_patterns = list(set(patterns))

        filtered_patterns = []
        for tag_pattern in unique_patterns:
            # Only go through additional filters if ALL is not applied.
            if TagPatternFilter.ALL not in tag_pattern.only:
                # Skip pattern marked as latest if not latest version.
                if TagPatternFilter.LATEST in tag_pattern.only and not self.is_latest:
                    continue
                # Skip pattern for primary OS if not primary OS.
                if TagPatternFilter.PRIMARY_OS in tag_pattern.only and not self.is_primary_os:
                    continue
                # Skip pattern for primary variant if not primary variant.
                if TagPatternFilter.PRIMARY_VARIANT in tag_pattern.only and not self.is_primary_variant:
                    continue

            filtered_patterns.append(tag_pattern)

        return filtered_patterns

    @property
    def tag_suffixes(self) -> list[str]:
        """Generate tag suffixes from set patterns."""
        tags = []
        for pattern in self.tag_patterns:
            rendered_tags = pattern.render(**self.tag_template_values)
            tags.extend(rendered_tags)

        # Ensure tags are unique and sorted
        tags = sorted(list(set(tags)))

        return tags

    @computed_field
    @property
    def tags(self) -> list[str]:
        """Generate tags for the image based on tag patterns."""
        tags = []
        if self.image_version.all_registries:
            for registry in self.image_version.all_registries:
                for suffix in self.tag_suffixes:
                    if hasattr(registry, "repository"):
                        tags.append(f"{registry.base_url}/{registry.repository}:{suffix}")
                    else:
                        tags.append(f"{registry.base_url}/{self.image_version.parent.name}:{suffix}")
        else:
            for suffix in self.tag_suffixes:
                tags.append(f"{self.image_version.parent.name}:{suffix}")

        return sorted(tags)

    @computed_field
    @property
    def ref(self) -> str:
        """Returns a reference to the image, preferring a build metadata digest if available."""
        if self.metadata_file is not None:
            return self.metadata_file.metadata.image_ref
        return self.tags[0]

    @computed_field
    @property
    def labels(self) -> dict[str, str]:
        """Generate labels for the image based on its properties."""
        labels = {
            f"{OCI_LABEL_PREFIX}.created": datetime.now().isoformat(),
            f"{OCI_LABEL_PREFIX}.source": str(self.repository.url),
            f"{OCI_LABEL_PREFIX}.title": self.image_version.parent.displayName,
            f"{OCI_LABEL_PREFIX}.vendor": self.repository.vendor,
            f"{POSIT_LABEL_PREFIX}.maintainer": str(self.repository.maintainer),
            f"{POSIT_LABEL_PREFIX}.name": self.image_version.parent.displayName,
        }
        if len(self.repository.authors) > 0:
            labels[f"{OCI_LABEL_PREFIX}.authors"] = ", ".join([str(author) for author in self.repository.authors])

        # Add common labels with both prefixes
        for prefix in [OCI_LABEL_PREFIX, POSIT_LABEL_PREFIX]:
            labels[f"{prefix}.version"] = self.image_version.name
            if self.repository.revision:
                labels[f"{prefix}.revision"] = self.repository.revision
            if self.image_version.parent.description:
                labels[f"{prefix}.description"] = self.image_version.parent.description
            if self.image_version.parent.documentationUrl:
                labels[f"{prefix}.documentation"] = str(self.image_version.parent.documentationUrl)

        if self.image_variant:
            labels[f"{POSIT_LABEL_PREFIX}.variant"] = self.image_variant.name
        if self.image_os:
            labels[f"{POSIT_LABEL_PREFIX}.os"] = self.image_os.name
        if self.image_version.dependencies:
            if not self.image_variant or (self.image_variant and self.image_variant.name != "Minimal"):
                for dependency in self.image_version.dependencies:
                    labels[f"{POSIT_LABEL_PREFIX}.tools.{dependency.dependency}"] = ", ".join(dependency.versions)

        return labels

    @property
    def cache_name(self) -> str | None:
        """Generate the image name and tag to use for a build cache."""
        if not self.settings.cache_registry:
            return None

        tag = re.sub(r"[+-].*", "", self.image_version.name)
        tag = re.sub(REGEX_IMAGE_TAG_SUFFIX_ALLOWED_CHARACTERS_PATTERN, "-", tag).strip("-._")
        if self.image_os:
            tag += f"-{self.image_os.tagDisplayName}"
        if self.image_variant:
            tag += f"-{self.image_variant.tagDisplayName}"
        cache_name = f"{self.settings.cache_registry}/{self.image_name}/cache:{tag}"

        return cache_name

    @property
    def temp_name(self) -> str | None:
        """Generate the image name and tag to use for temporary image storage in multiplatform split/merge builds."""
        if not self.settings.temp_registry:
            return None

        return f"{self.settings.temp_registry}/{self.image_name}/tmp"

    def remove(self, prune: bool = True, force: bool = False):
        """Remove the image from the local image cache or registry."""
        for tag in self.tags:
            if python_on_whales.docker.image.exists(tag):
                log.info(f"Deleting image '{tag}' from local cache.")
                python_on_whales.docker.image.remove(tag, prune=prune, force=force)

    def load_build_metadata_from_file(self, metadata_file: Path):
        """Load build metadata from a given file."""
        self.metadata_file = MetadataFile(target_uid=self.uid, filepath=metadata_file)

    def build(
        self,
        load: bool = True,
        push: bool = False,
        cache: bool = True,
        platforms: list[str] | None = None,
        metadata_file: Path | bool | None = None,
    ) -> python_on_whales.Image | None:
        """Build the image using the Containerfile and return the built image."""
        if not (self.context.base_path / self.containerfile).is_file():
            raise BakeryFileError(
                f"Containerfile not found for '{str(self)}' at expected path: "
                f"{str(self.context.base_path / self.containerfile)}",
                filepath=self.containerfile,
            )

        cache_from = None
        cache_to = None
        if self.cache_name is not None:
            cache_from = f"type=registry,ref={self.cache_name}"
            cache_to = f"{cache_from},mode=max"

        if isinstance(metadata_file, bool) and metadata_file:
            metadata_file = SETTINGS.temporary_storage / f"{self.uid}.json"

        tags = self.tags
        output = {}
        if self.temp_name is not None:
            tags = [self.temp_name]
            # If push is true for a temporary image, override the output to push the image by digest.
            if push:
                output = {"type": "image", "push-by-digest": True, "name-canonical": True, "push": True}
                push = False

        # This context manager is **NOT** thread-safe. If we implement this as parallel in the future, the working
        # directory change should be managed at a higher level.
        with contextlib.chdir(self.context.base_path):
            log.info(f"Building image '{str(self)}'")
            try:
                image = python_on_whales.docker.build(
                    context_path=self.context.base_path,
                    file=self.containerfile,
                    tags=tags,
                    labels=self.labels,
                    load=load,
                    push=push,
                    output=output,
                    cache=cache,
                    cache_from=cache_from,
                    cache_to=cache_to,
                    metadata_file=metadata_file,
                    platforms=platforms or self.image_os.platforms,
                )
            except python_on_whales.exceptions.DockerException as e:
                raise BakeryToolRuntimeError(
                    message=f"Failed to build image '{str(self)}'",
                    tool_name="docker",  # FIXME: This should be dynamic based on the tool used. Not sure how to get.
                    cmd=e.docker_command,
                    stdout=e.stdout,
                    stderr=e.stderr,
                    exit_code=e.return_code,
                    metadata={"image_target": str(self)},
                )

        log.info(f"Successfully built image '{str(self)}'")

        if isinstance(metadata_file, Path):
            log.debug(f"Loading in build metadata from file {str(metadata_file)}")
            self.metadata_file = MetadataFile(target_uid=self.uid, filepath=metadata_file)

        return image

    def merge(self, sources: list[str], dry_run: bool = False) -> Manifest:
        """Merge multiple images into a single image, tag, and push."""
        if dry_run:
            return python_on_whales.docker.buildx.imagetools.create(
                sources=sources,
                tags=self.tags,
                dry_run=dry_run,
            )

        with RegistryContainer() as registry:
            temp_tag = f"{registry.url}/{self.uid}:latest"
            log.debug(f"Merging sources for {self.uid}...")
            log.debug(f"Pushing merged image to temporary tag '{temp_tag}'...")
            python_on_whales.docker.buildx.imagetools.create(
                sources=sources,
                tags=[temp_tag],
                dry_run=dry_run,
            )

            manifest = inspect_image(temp_tag)
            index_ref = f"{temp_tag}@{manifest.digest}"
            platforms = [str(m.platform) for m in manifest.manifests]

            log.debug("Pulling merged image...")
            for platform in platforms:
                python_on_whales.docker.image.pull(
                    temp_tag,
                    quiet=False if SETTINGS.log_level == logging.DEBUG else True,
                    platform=platform,
                )
            python_on_whales.docker.image.pull(index_ref, quiet=False if SETTINGS.log_level == logging.DEBUG else True)

            log.debug("Applying tags...")
            for tag in self.tags:
                python_on_whales.docker.image.tag(index_ref, tag)

            log.info(f"Pushing image {self.uid}...")
            python_on_whales.docker.image.push(self.tags, quiet=False if SETTINGS.log_level == logging.DEBUG else True)

        return python_on_whales.docker.buildx.imagetools.inspect(self.tags[0])
