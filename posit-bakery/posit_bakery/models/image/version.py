from copy import deepcopy
from pathlib import Path
from typing import List

from pydantic import BaseModel


from posit_bakery.models.image import ImageMetadata
from posit_bakery.models.image.variant import ImageVariant
from posit_bakery.models.manifest.build import ManifestBuild
from posit_bakery.models.manifest.target import ManifestTarget
from posit_bakery.templating.default import render_image_templates


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
                meta_var: ImageMetadata = deepcopy(meta)
                meta_var.goss = target.goss

                variants.append(
                    ImageVariant.load(
                        meta=meta_var,
                        latest=build.latest,
                        _os=_os,
                        target=_type,
                    )
                )

        return cls(version=meta.version, context=meta.context, variants=variants)

    @classmethod
    def create(cls, image_context: Path, version: str, targets: List[str], mark_latest: bool):
        context: Path = image_context / version
        render_image_templates(
            context=context,
            version=version,
            targets=targets,
            latest=mark_latest,
        )

        # TODO: Pull in the variants after render
        return cls(version=version, context=context)
