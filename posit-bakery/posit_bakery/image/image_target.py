import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Self

import python_on_whales
from pydantic import BaseModel, field_validator, computed_field, model_validator

from posit_bakery.config.image import ImageVersion, ImageVariant, ImageVersionOS
from posit_bakery.config.repository import Repository
from posit_bakery.config.tag import TagPattern, TagPatternFilter
from posit_bakery.const import OCI_LABEL_PREFIX, POSIT_LABEL_PREFIX


class ImageBuildStrategy(str, Enum):
    """Enumeration for image build strategies."""

    BUILD = "build"  # Build using sequential build calls to builder
    BAKE = "bake"  # Build using Docker BuildKit bake


class ImageTargetContext(BaseModel):
    base_path: Path
    image_path: Path
    version_path: Path


class ImageTarget(BaseModel):
    context: ImageTargetContext
    repository: Repository
    image_version: ImageVersion
    image_variant: ImageVariant | None = None
    image_os: ImageVersionOS | None = None
    tag_patterns: list[TagPattern]

    @classmethod
    def new_image_target(
        cls,
        repository: Repository,
        image_version: ImageVersion,
        image_variant: ImageVariant | None = None,
        image_os: ImageVersionOS | None = None,
    ) -> "ImageTarget":
        """Create a new ImageTarget instance from a repository, version, variant, and OS combination."""
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
            registries=image_version.registries,
            tag_patterns=[*image_variant.parent.tagPatterns, *image_variant.tagPatterns],
        )

    def __str__(self):
        s = f"{self.image_version.parent.name} / " f"{self.image_version.name}"
        if self.image_variant:
            s += f" / {self.image_variant.name}"
        if self.image_os:
            s += f" / {self.image_os.name}"
        return s

    @computed_field
    @property
    def uid(self) -> str:
        """Generate a unique identifier for the target based on its properties."""
        u = f"{self.image_name}-{self.image_version}"
        if self.image_variant:
            u += f"-{self.image_variant}"
        if self.image_os:
            u += f"-{self.image_os}"
        return re.sub("[.+/]", "-", u)

    @computed_field
    @property
    def image_name(self) -> str:
        """Return the name of the image."""
        return self.image_version.parent.name

    @computed_field
    @property
    def is_latest(self) -> bool:
        return self.image_version.latest

    @computed_field
    @property
    def is_primary_os(self) -> bool:
        if self.image_os is None:
            return False
        return self.image_os.primary

    @computed_field
    @property
    def is_primary_variant(self) -> bool:
        if self.image_variant is None:
            return False
        return self.image_variant.primary

    @computed_field
    @property
    def containerfile(self) -> Path:
        """Return the path of the Containerfile for this image target."""
        if not self.context.version_path:
            raise ValueError("Version path is not set in the context.")
        containerfile_name = "Containerfile"
        if self.image_os and self.image_os.extension:
            containerfile_name += f".{self.image_os.extension}"
        if self.image_variant and self.image_variant.extension:
            containerfile_name += f".{self.image_variant.extension}"

        expected_path = self.context.version_path / containerfile_name
        if not expected_path.is_file():
            raise FileNotFoundError(f"Containerfile '{expected_path}' does not exist for {str(self)}.")

        if expected_path.is_absolute():
            expected_path = expected_path.relative_to(self.context.base_path)

        return expected_path

    @computed_field
    @property
    def tag_template_values(self) -> dict[str, str]:
        """Return a dictionary of values for templating tags."""
        return {
            "Version": self.image_version.name,
            "Variant": self.image_variant.tagDisplayName if self.image_variant else "",
            "OS": self.image_os.tagDisplayName if self.image_os else "",
            "Name": self.image_name,
        }

    @field_validator("tag_patterns", mode="after")
    def deduplicate_tag_patterns(cls, tag_patterns: list[TagPattern]) -> list[TagPattern]:
        """Ensure tag patterns are unique."""
        unique_patterns = set(tag_patterns)
        return list(unique_patterns)

    @model_validator(mode="after")
    def filter_tag_patterns(self) -> Self:
        """Apply filters to tag patterns based on the image properties."""
        filtered_patterns = []
        for tag_pattern in self.tag_patterns:
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

        self.tag_patterns = filtered_patterns

        return self

    @computed_field
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
        for registry in self.image_version.all_registries:
            for suffix in self.tag_suffixes:
                tags.append(f"{registry.base_url}/{self.image_version.parent.name}:{suffix}")

        return tags

    @computed_field
    @property
    def labels(self) -> dict[str, str]:
        """Generate labels for the image based on its properties."""
        labels = {
            f"{OCI_LABEL_PREFIX}.created": datetime.now().isoformat(),
            f"{OCI_LABEL_PREFIX}.source": self.repository.url,
            f"{OCI_LABEL_PREFIX}.title": self.image_version.parent.displayName,
            f"{OCI_LABEL_PREFIX}.vendor": self.repository.vendor,
            f"{OCI_LABEL_PREFIX}.authors": ", ".join([str(author) for author in self.repository.authors]),
            f"{POSIT_LABEL_PREFIX}.maintainer": self.repository.maintainer,
            f"{OCI_LABEL_PREFIX}.name": self.image_version.parent.displayName,
        }
        # Add common labels with both prefixes
        for prefix in [OCI_LABEL_PREFIX, POSIT_LABEL_PREFIX]:
            labels[f"{prefix}.version"] = self.image_version.name
            if self.repository.revision:
                labels[f"{prefix}.revision"] = self.repository.revision
            if self.image_version.parent.description:
                labels[f"{prefix}.description"] = self.image_version.parent.description
            if self.image_version.parent.documentationUrl:
                labels[f"{prefix}.documentation"] = self.image_version.parent.documentationUrl

        if self.image_variant:
            labels[f"{POSIT_LABEL_PREFIX}.variant"] = self.image_variant.name
        if self.image_os:
            labels[f"{POSIT_LABEL_PREFIX}.os"] = self.image_os.name

        return labels

    def build(self, load: bool = True, push: bool = False, cache: bool = True) -> python_on_whales.Image | None:
        """Build the image using the Containerfile and return the built image."""
        image = python_on_whales.docker.build(
            context_path=self.context.base_path,
            file=str(self.containerfile),
            tags=self.tags,
            labels=self.labels,
            load=load,
            push=push,
            cache=cache,
        )

        return image
