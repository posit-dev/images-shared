from copy import deepcopy
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel

from posit_bakery.models.image import ImageLabels, ImageMetadata
from posit_bakery.models.image.variant import ImageVariant
from posit_bakery.models.image.version import ImageVersion
from posit_bakery.models.manifest.document import ManifestDocument


class Image(BaseModel):
    name: str
    context: Path
    versions: List[ImageVersion]

    @classmethod
    def load(cls, context: Path, manifest: ManifestDocument):
        meta: ImageMetadata = ImageMetadata(
            name=manifest.image_name,
            labels=ImageLabels(
                posit={"name": manifest.image_name},
                oci={"title": manifest.image_name},
            ),
        )

        versions: List[ImageVersion] = []
        for version, build in manifest.build.items():
            # Set unique metadata for each version
            meta = deepcopy(meta)
            meta.version = version
            meta.context = context / version
            meta.labels.posit["version"] = version

            versions.append(
                ImageVersion.load(
                    meta=meta,
                    build=build,
                    targets=manifest.target,
                )
            )

        return cls(name=manifest.image_name, context=context, versions=versions)

    @property
    def variants(self) -> List[ImageVariant]:
        return [variant for version in self.versions for variant in version.variants]
