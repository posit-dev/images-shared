from pathlib import Path
from typing import List

from pydantic import BaseModel

from posit_bakery.models import ManifestDocument
from posit_bakery.models.manifest.build import ManifestBuild
from posit_bakery.models.manifest.target import ManifestTarget


class ImageVariant(BaseModel):
    latest: bool = False
    context: str = None
    containerfile: Path = None


class ImageVersion(BaseModel):
    version: str
    context: Path
    variants: List[ImageVariant] = []

    @classmethod
    def load(cls, version: str, build: ManifestBuild, targets: List[ManifestTarget]):
        variants: List[ImageVariant] = []
        for _os in build.os:
            for target in targets:
                variants.append(ImageVariant(latest=build.latest))

        return cls(version=version, variants=variants)


class Image(BaseModel):
    name: str
    context: Path
    versions: List[ImageVersion] = []

    @classmethod
    def load(cls, manifest: ManifestDocument):
        versions: List[ImageVersion] = []
        for version, build in manifest.build.items():
            versions.append(ImageVersion.load(version, build, manifest.target))

        return cls(name=manifest.image_name, versions=versions)

    @property
    def targets(self):
        return [variant for version in self.versions for variant in version.variants]
