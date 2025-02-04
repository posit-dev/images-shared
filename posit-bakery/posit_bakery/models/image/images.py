from copy import copy, deepcopy
from typing import Dict, List

from pydantic import BaseModel

from posit_bakery.error import BakeryImageNotFoundError
from posit_bakery.models.config.config import Config
from posit_bakery.models.image.image import Image
from posit_bakery.models.image.variant import ImageVariant
from posit_bakery.models.image.version import ImageVersion
from posit_bakery.models.manifest.manifest import Manifest


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

        for name, manifest in manifests.items():
            image: Image = Image.load(manifest.context, manifest.model)
            for variant in image.variants:
                variant.complete_metadata(config=config.model, commit=config.commit)

            images[name] = image

        return cls(**images)

    @property
    def variants(self) -> List[ImageVariant]:
        vars: List[ImageVariant] = []
        for image in self.values():
            vars.extend(copy(image.variants))

        return vars

    def filter(self, filter: ImageFilter = ImageFilter()) -> dict[str, Image]:
        images: dict[str, Image] = {}
        for image_name, image in self.items():
            if filter.image_name is not None and filter.image_name != image.name:
                continue

            versions: List[ImageVersion] = []
            for version in image.versions:
                if filter.image_version is not None and filter.image_version != version.version:
                    continue

                variants: List[ImageVariant] = []
                for variant in version.variants:
                    if filter.is_latest is not None and filter.is_latest != variant.latest:
                        continue
                    if filter.build_os is not None and filter.build_os != variant.os:
                        continue
                    if filter.target_type is not None and filter.target_type != variant.target:
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
            raise BakeryImageNotFoundError("No images found for filter.")

        return Images(**images)
