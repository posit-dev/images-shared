from copy import copy, deepcopy
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel

from posit_bakery.error import BakeryFileNotFoundError
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


class ImageLabels(BaseModel):
    posit: Dict[str, str] = {}
    oci: Dict[str, str] = {}
    posit_prefix: str = "co.posit.image"
    oci_prefix: str = "org.opencontainers.image"


class ImageGoss(BaseModel):
    deps: Path
    tests: Path
    command: str
    wait: int

    @classmethod
    def load(cls, context: Path, goss: ManifestGoss = ManifestGoss()):
        deps: Path
        tests: Path

        # TODO: Handle when paths are over-ridden in ManifestGoss
        if (context / "deps").is_dir():
            deps = context / "deps"
        elif (context.parent / "deps").is_dir():
            deps = context.parent / "deps"
        elif (context.parent.parent / "deps").is_dir():
            deps = context.parent.parent / "deps"
        else:
            raise BakeryFileNotFoundError(f"Could not find 'deps' directory for goss files. context: '{context}'.")

        if (context / "test").is_dir():
            tests = context / "test"
        elif (context.parent / "test").is_dir():
            tests = context.parent / "test"
        elif (context.parent.parent / "test").is_dir():
            tests = context.parent.parent / "test"
        else:
            raise BakeryFileNotFoundError(f"Could not find 'test' directory for goss files. context: '{context}'.")

        return cls(deps=deps, tests=tests, command=goss.command, wait=goss.wait)


class ImageVariant(BaseModel):
    latest: bool
    os: str
    target: str
    containerfile: Path
    labels: ImageLabels = ImageLabels()
    tags: List[str] = []
    goss: ImageGoss

    @classmethod
    def load(
        cls,
        context: Path,
        version: str,
        latest: bool,
        _os: str,
        target: str,
        goss: ManifestGoss = ManifestGoss(),
        labels: ImageLabels | None = None,
    ):
        build_os: BuildOS = find_os(_os)
        containerfile = cls.find_containerfile(context, _os, target)
        if labels is None:
            labels = ImageLabels
        labels.posit["os"] = _os
        labels.posit["type"] = target

        # TODO: Handle min vs std
        tags: List[str] = [f"{version}-{target}", f"{version}-{build_os.image_tag}-{target}"]
        if latest:
            tags += [
                f"{build_os.image_tag}-{target}",
                "latest",
            ]

        return cls(
            latest=latest,
            os=_os,
            target=target,
            containerfile=containerfile,
            labels=labels,
            tags=tags,
            goss=ImageGoss.load(context, goss),
        )

    @staticmethod
    def find_containerfile(context: Path, _os: str, target: str):
        build_os: BuildOS = find_os(_os)
        if build_os is None:
            raise ValueError(f"Operating system '{_os}' is not supported.")

        # Possible patterns
        filepaths: List[Path] = [
            context / f"Containerfile.{build_os.condensed}.{target}",
            context / f"Containerfile.{target}",
            context / f"Containerfile.{build_os.condensed}",
            context / f"Containerfile",
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
            for _type, target in targets.items():
                variants.append(
                    ImageVariant.load(
                        context=version_context,
                        version=version,
                        latest=build.latest,
                        _os=_os,
                        target=_type,
                        goss=target.goss,
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
    def variants(self) -> List[ImageVariant]:
        return [variant for version in self.versions for variant in version.variants]


class Images(dict):
    @classmethod
    def load(cls, manifests: Dict[str, Manifest]) -> dict[str, Image]:
        images: dict[str, Image] = {}

        for name, manifest in manifests.items():
            images[name] = Image.load(manifest.context, manifest.model)

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
            raise ValueError("No images found for filter.")

        return Images(**images)
