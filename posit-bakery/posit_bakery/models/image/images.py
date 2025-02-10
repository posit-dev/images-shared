import logging
from copy import copy, deepcopy
from typing import Dict, List

import pydantic
from pydantic import BaseModel

from posit_bakery.error import (
    BakeryImageNotFoundError,
    BakeryModelValidationError,
    BakeryModelValidationErrorGroup,
)
from posit_bakery.models.config.config import Config
from posit_bakery.models.image.image import Image
from posit_bakery.models.image.variant import ImageVariant
from posit_bakery.models.image.version import ImageVersion
from posit_bakery.models.manifest.manifest import Manifest

log = logging.getLogger(__name__)


class ImageFilter(BaseModel):
    image_name: str | None = None
    image_version: str | None = None
    is_latest: bool | None = None
    build_os: str | None = None
    target_type: str | None = None

    def __bool__(self) -> bool:
        """ImageFilter is truthy if any of its values are not None"""
        return any([v is not None for v in self.model_dump().values()])


class Images(dict):
    @classmethod
    def load(cls, config: Config, manifests: Dict[str, Manifest]) -> dict[str, Image]:
        images: dict[str, Image] = {}
        error_list = []

        for name, manifest in manifests.items():
            try:
                image: Image = Image.load(manifest.context, manifest.model)
            except pydantic.ValidationError as e:
                # TODO: Make this less goofy
                # This was the only obvious way I could find to chain the exception from the pydantic error and still
                # group it into the error_list for the BakeryModelValidationErrorGroup.
                log.error(f"Validation error occurred loading image from manifest: {manifest.filepath}")
                try:
                    raise BakeryModelValidationError(
                        model_name="Image",
                        filepath=manifest.filepath,
                    ) from e
                except BakeryModelValidationError as e:
                    error_list.append(e)
                continue
            for variant in image.variants:
                variant.complete_metadata(config=config.model, commit=config.commit)

            images[name] = image

        if error_list:
            if len(error_list) == 1:
                raise error_list[0]
            raise BakeryModelValidationErrorGroup(
                "Multiple validation errors occurred while processing Images from manifest.", error_list
            )

        return cls(**images)

    @property
    def variants(self) -> List[ImageVariant]:
        vars: List[ImageVariant] = []
        for image in self.values():
            vars.extend(copy(image.variants))

        return vars

    def filter(self, _filter: ImageFilter = ImageFilter()) -> dict[str, Image]:
        images: dict[str, Image] = {}
        for image_name, image in self.items():
            if _filter.image_name is not None and _filter.image_name != image.name:
                continue

            versions: List[ImageVersion] = []
            for version in image.versions:
                if _filter.image_version is not None and _filter.image_version != version.version:
                    continue

                variants: List[ImageVariant] = []
                for variant in version.variants:
                    if _filter.is_latest is not None and _filter.is_latest != variant.latest:
                        continue
                    if _filter.build_os is not None and _filter.build_os != variant.os:
                        continue
                    if _filter.target_type is not None and _filter.target_type != variant.target:
                        continue

                    variants.append(deepcopy(variant))

                if variants:
                    ver = copy(version)
                    ver.variants = variants
                    versions.append(ver)

            if versions:
                img = copy(image)
                img.versions = versions
                images[image_name] = img

        if not images:
            log.error(f"No images found for filter.")
            raise BakeryImageNotFoundError("No images found for filter.")

        return Images(**images)
