from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel

from posit_bakery.error import BakeryFileNotFoundError
from posit_bakery.util import find_in_context
from posit_bakery.models.config.document import ConfigDocument
from posit_bakery.models.image.image import ImageMetadata
from posit_bakery.models.manifest import find_os
from posit_bakery.models.manifest.build_os import BuildOS
from posit_bakery.models.manifest.goss import ManifestGoss


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
