from copy import copy, deepcopy
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel

from posit_bakery.error import BakeryError, BakeryFileNotFoundError
from posit_bakery.util import find_in_context
from posit_bakery.models.config.config import Config
from posit_bakery.models.config.document import ConfigDocument
from posit_bakery.models.manifest import find_os
from posit_bakery.models.manifest.build import ManifestBuild
from posit_bakery.models.manifest.build_os import BuildOS
from posit_bakery.models.manifest.document import ManifestDocument
from posit_bakery.models.manifest.goss import ManifestGoss
from posit_bakery.models.manifest.manifest import Manifest
from posit_bakery.models.manifest.target import ManifestTarget


class ImageFilter(BaseModel):
    image_name: str | None = None
    image_version: str | None = None
    is_latest: bool | None = None
    build_os: str | None = None
    target_type: str | None = None

    def __bool__(self) -> bool:
        """ImageFilter is truthy if any of its values are not None"""
        return any([v is not None for v in self.model_dump().values()])


class ImageLabels(BaseModel):
    posit: Dict[str, str] = {}
    oci: Dict[str, str] = {}
    posit_prefix: str = "co.posit.image"
    oci_prefix: str = "org.opencontainers.image"


class ImageMetadata(BaseModel):
    name: str
    version: str = None
    context: Path = None
    labels: ImageLabels = ImageLabels()
    tags: List[str] = []
    goss: ManifestGoss = ManifestGoss()


class ImageGoss(BaseModel):
    deps: Path
    tests: Path
    command: str
    wait: int

    @classmethod
    def load(cls, context: Path, goss: ManifestGoss = ManifestGoss()):
        # TODO: Handle when paths are over-ridden in ManifestGoss
        deps: Path = find_in_context(context=context, name="deps", _type="dir", parents=3)
        tests: Path = find_in_context(context=context, name="test", _type="dir", parents=3)

        return cls(deps=deps, tests=tests, command=goss.command, wait=goss.wait)


class ImageVariant(BaseModel):
    meta: ImageMetadata
    latest: bool
    os: str
    target: str
    containerfile: Path
    goss: ImageGoss = None
    # Labels and tags require combining the Config metadata
    labels: Dict[str, str] = {}
    tags: List[str] = []

    @classmethod
    def load(
        cls,
        meta: ImageMetadata,
        latest: bool,
        _os: str,
        target: str,
    ):
        build_os: BuildOS = find_os(_os)
        containerfile = cls.find_containerfile(meta.context, _os, target)

        meta.labels.posit["os"] = _os
        meta.labels.posit["type"] = target

        # TODO: Handle min vs std
        meta.tags = [
            f"{meta.version}-{build_os.image_tag}-{target}",
            f"{meta.version}-{target}",
        ]
        if latest:
            meta.tags += [
                f"{build_os.image_tag}-{target}",
                "latest",
            ]

        return cls(
            meta=meta,
            latest=latest,
            os=_os,
            target=target,
            containerfile=containerfile,
            goss=ImageGoss.load(meta.context, meta.goss),
        )

    @staticmethod
    def find_containerfile(context: Path, _os: str, target: str):
        build_os: BuildOS = find_os(_os)
        if build_os is None:
            raise ValueError(f"Operating system '{_os}' is not supported.")

        # Possible patterns
        filenames: List[str] = [
            f"Containerfile.{build_os.condensed}.{target}",
            f"Containerfile.{target}",
            f"Containerfile.{build_os.condensed}",
            f"Containerfile",
        ]
        for name in filenames:
            try:
                filepath = find_in_context(context, name)
                return filepath
            except BakeryFileNotFoundError:
                continue

        raise BakeryFileNotFoundError(f"Containerfile not found. context: '{context}',  os: '{_os}', target: {target}.")

    def complete_metadata(self, config: ConfigDocument, commit: str = None) -> None:
        labels: Dict[str, str] = {}
        labels.update({f"{self.meta.labels.oci_prefix}.{k}": v for k, v in self.meta.labels.oci.items()})
        labels.update(
            {
                f"{self.meta.labels.oci_prefix}.vendor": config.repository.vendor,
                f"{self.meta.labels.oci_prefix}.maintainer": config.repository.maintainer,
                f"{self.meta.labels.oci_prefix}.revision": commit if commit else "",
                f"{self.meta.labels.oci_prefix}.authors": ", ".join(config.repository.authors),
                f"{self.meta.labels.oci_prefix}.source": config.repository.url,
            }
        )
        labels.update({f"{self.meta.labels.posit_prefix}.{k}": v for k, v in self.meta.labels.posit.items()})

        self.labels = labels
        self.tags = [f"{reg.base_url}/{self.meta.name}:{tag}" for reg in config.registries for tag in self.meta.tags]


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
            raise BakeryError("No images found for filter.")

        return Images(**images)
