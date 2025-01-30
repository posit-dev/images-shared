from copy import deepcopy
from pathlib import Path
from typing import List

from pydantic import BaseModel


from posit_bakery.models.image.image import ImageMetadata
from posit_bakery.models.image.variant import ImageVariant
from posit_bakery.models.manifest.build import ManifestBuild
from posit_bakery.models.manifest.target import ManifestTarget


class ImageVersion(BaseModel):
    version: str
    context: Path
    variants: List[ImageVariant] = []

    @classmethod
    def load(
        cls,
        meta: ImageMetadata,
        build: ManifestBuild,
        targets: List[ManifestTarget],
    ):
        variants: List[ImageVariant] = []
        for _os in build.os:
            for _type, target in targets.items():
                # Unique metadata for each variant
                meta = deepcopy(meta)
                meta.goss = target.goss

                variants.append(
                    ImageVariant.load(
                        meta=meta,
                        latest=build.latest,
                        _os=_os,
                        target=_type,
                    )
                )

        return cls(version=meta.version, context=meta.context, variants=variants)
