import logging
import os
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel

from posit_bakery.error import BakeryFileError
from posit_bakery.templating.filters import condense
from posit_bakery.util import find_in_context
from posit_bakery.models.config.document import ConfigDocument
from posit_bakery.models.image.image import ImageMetadata
from posit_bakery.models.image.tags import default_tags
from posit_bakery.models.manifest import find_os
from posit_bakery.models.manifest.build_os import BuildOS
from posit_bakery.models.manifest.goss import ManifestGoss

log = logging.getLogger(__name__)


class ImageGoss(BaseModel):
    deps: Path | None
    tests: Path
    command: str
    wait: int

    @staticmethod
    def _parse_path(context: Path, name: str, value: str | bool | None) -> Path | None:
        if value is None:
            return find_in_context(context=context, name=name, _type="dir", parents=3)
        elif isinstance(value, bool):
            if value:
                return find_in_context(context=context, name=name, _type="dir", parents=3)
            else:
                return None
        elif isinstance(value, str):
            # FIXME: This still has a shortcoming. It cannot process any Jinja2 variables because it lacks additional
            #        context to resolve them.
            if os.sep in value:
                path = context / value
                if path.exists(follow_symlinks=True) and path.is_dir():
                    return path
                else:
                    raise BakeryFileError(
                        f"Path '{value}' for Goss path '{name}' does not exist or is not a directory."
                    )
            else:
                return find_in_context(context=context, name=value, _type="dir", parents=3)
        else:
            raise BakeryFileError(
                f"Invalid value '{value}' for Goss path '{name}'. Expected None, bool, or str."
            )

    @classmethod
    def load(cls, context: Path, goss: ManifestGoss = ManifestGoss()):
        deps: Path | None = cls._parse_path(context, "deps", goss.deps)
        tests: Path | None = cls._parse_path(context, "test", goss.path)

        if tests is None:
            raise BakeryFileError("Goss tests path is required and cannot be None.")

        return cls(deps=deps, tests=tests, command=goss.command, wait=goss.wait)


class ImageVariant(BaseModel):
    meta: ImageMetadata
    latest: bool
    os: str
    target: str
    containerfile: Path
    goss: ImageGoss | None = None
    snyk_policy_file: Path | None = None
    # Labels and tags require combining the Config metadata
    labels: Dict[str, str] = {}
    tags: List[str] = []

    @classmethod
    def load(
        cls,
        meta: ImageMetadata,
        latest: bool,
        _os: str,
        _os_primary: str,
        target: str,
    ):
        build_os: BuildOS = find_os(_os)
        primary_os: BuildOS = find_os(_os_primary)
        containerfile = cls.find_containerfile(meta.context, _os, target)

        meta.labels.posit["os"] = _os
        meta.labels.posit["type"] = target

        meta.tags = default_tags(
            version=meta.version,
            _os=build_os.image_tag,
            target=target,
            is_latest=latest,
            is_primary_os=(build_os == primary_os),
        )

        try:
            snyk_policy_file: Path = find_in_context(context=meta.context, name=".snyk", _type="file", parents=2)
        except BakeryFileError:
            snyk_policy_file = None

        return cls(
            meta=meta,
            latest=latest,
            os=_os,
            target=target,
            containerfile=containerfile,
            goss=ImageGoss.load(meta.context, meta.goss),
            snyk_policy_file=snyk_policy_file,
        )

    @staticmethod
    def find_containerfile(context: Path, _os: str, target: str):
        build_os: BuildOS = find_os(_os)
        if build_os is None:
            log.warning(
                f"Could not match '{_os}' to a supported OS. Bakery will still attempt to find a Containerfile, but "
                f"unexpected behavior may occur."
            )
            condensed_build_os = condense(_os)
        else:
            condensed_build_os = build_os.condensed

        # Possible patterns
        filenames: List[str] = [
            f"Containerfile.{condensed_build_os}.{target}",
            f"Containerfile.{target}",
            f"Containerfile.{condensed_build_os}",
            f"Containerfile",
        ]
        log.debug(f"Searching for Containerfile in {context} with patterns: {", ".join(filenames)}")
        for name in filenames:
            try:
                filepath = find_in_context(context, name)
                log.debug(f"Found Containerfile: {filepath}")
                return filepath
            except BakeryFileError:
                continue

        log.error(f"Could not find a Containerfile for os '{_os}', target {target}.")
        raise BakeryFileError(
            f"Containerfile not found for os '{_os}', target {target}.", [(context / f) for f in filenames]
        )

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
