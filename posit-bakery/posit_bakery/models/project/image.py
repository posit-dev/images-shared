from pathlib import Path
from typing import List

from pydantic import BaseModel

from posit_bakery.error import BakeryFileNotFoundError
from posit_bakery.models import Manifest, ManifestDocument
from posit_bakery.models.manifest import find_os
from posit_bakery.models.manifest.build import ManifestBuild
from posit_bakery.models.manifest.build_os import BuildOS
from posit_bakery.models.manifest.target import ManifestTarget


class ImageVariant(BaseModel):
    latest: bool
    os: str
    target: str
    containerfile: Path

    @classmethod
    def load(cls, context: Path, latest: bool, _os: str, target: str):
        containerfile = cls.find_containerfile(context, _os, target)

        return cls(latest=latest, os=_os, target=target, containerfile=containerfile)

    @staticmethod
    def find_containerfile(context: Path, _os: str, target: str):
        build_os: BuildOS = find_os(_os)
        if build_os is None:
            raise ValueError(f"Operating system '{_os}' is not supported.")

        # Possible patterns
        filepaths: List[Path] = [
            context / f"Containerfile.{build_os.condensed}.{target}",
            context / f"Containerfile.{target}",
        ]
        for filepath in filepaths:
            if filepath.is_file():
                return filepath

        raise BakeryFileNotFoundError(f"Containerfile not found. context: '{context}',  os: '{_os}', target: {target}.")


class ImageVersion(BaseModel):
    version: str
    context: Path
    variants: List[ImageVariant] = []

    @classmethod
    def load(cls, version: str, context: Path, build: ManifestBuild, targets: List[ManifestTarget]):
        version_context: Path = context / version
        variants: List[ImageVariant] = []
        for _os in build.os:
            for target in targets:
                variants.append(
                    ImageVariant.load(
                        context=version_context,
                        latest=build.latest,
                        _os=_os,
                        target=target,
                    )
                )

        return cls(version=version, context=version_context, variants=variants)


class Image(BaseModel):
    name: str
    context: Path
    versions: List[ImageVersion]

    @classmethod
    def load(cls, context: Path, manifest: ManifestDocument):
        versions: List[ImageVersion] = []
        for version, build in manifest.build.items():
            versions.append(ImageVersion.load(version=version, context=context, build=build, targets=manifest.target))

        return cls(name=manifest.image_name, context=context, versions=versions)

    @property
    def targets(self):
        return [variant for version in self.versions for variant in version.variants]
