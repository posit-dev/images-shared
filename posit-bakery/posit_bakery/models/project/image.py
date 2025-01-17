from copy import deepcopy
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel

from posit_bakery.error import BakeryFileNotFoundError
from posit_bakery.models import Manifest, ManifestDocument
from posit_bakery.models.manifest import find_os
from posit_bakery.models.manifest.build import ManifestBuild
from posit_bakery.models.manifest.build_os import BuildOS
from posit_bakery.models.manifest.target import ManifestTarget


class ImageLabels(BaseModel):
    posit: Dict[str, str] = {}
    oci: Dict[str, str] = {}
    posit_prefix: str = "co.posit.image"
    oci_prefix: str = "org.opencontainers.image"


class ImageVariant(BaseModel):
    latest: bool
    os: str
    target: str
    containerfile: Path
    labels: ImageLabels = ImageLabels()
    tags: List[str] = []

    @classmethod
    def load(
        cls,
        context: Path,
        version: str,
        latest: bool,
        _os: str,
        target: str,
        labels: ImageLabels | None = None,
    ):
        build_os: BuildOS = find_os(_os)
        containerfile = cls.find_containerfile(context, _os, target)
        if labels is None:
            labels = ImageLabels()
        labels.posit["os"] = _os
        labels.posit["type"] = target

        # TODO: Handle min vs std
        tags: List[str] = [f"{version}-{target}", f"{version}-{build_os.image_tag}-{target}"]
        if latest:
            tags += [
                f"{build_os.image_tag}-{target}",
                "latest",
            ]

        return cls(latest=latest, os=_os, target=target, containerfile=containerfile, labels=labels, tags=tags)

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
    def load(
        cls,
        version: str,
        context: Path,
        build: ManifestBuild,
        targets: List[ManifestTarget],
        labels: ImageLabels,
    ):
        version_context: Path = context / version
        variants: List[ImageVariant] = []
        labels.posit["version"] = version

        for _os in build.os:
            for target in targets:
                variants.append(
                    ImageVariant.load(
                        context=version_context,
                        version=version,
                        latest=build.latest,
                        _os=_os,
                        target=target,
                        labels=deepcopy(labels),
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
        labels: ImageLabels = ImageLabels(
            posit={"name": manifest.image_name},
            # TODO: Add created time
            oci={"title": manifest.image_name},
        )

        for version, build in manifest.build.items():
            versions.append(
                ImageVersion.load(
                    version=version,
                    context=context,
                    build=build,
                    targets=manifest.target,
                    labels=deepcopy(labels),
                )
            )

        return cls(name=manifest.image_name, context=context, versions=versions)

    @property
    def targets(self):
        return [variant for version in self.versions for variant in version.variants]
