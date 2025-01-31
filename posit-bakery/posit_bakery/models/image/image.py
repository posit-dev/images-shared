from copy import deepcopy
from pathlib import Path
from typing import List

from pydantic import BaseModel

from posit_bakery.models.image import ImageLabels, ImageMetadata
from posit_bakery.models.image.variant import ImageVariant
from posit_bakery.models.image.version import ImageVersion
from posit_bakery.models.manifest import guess_os_list
from posit_bakery.models.manifest.build_os import BuildOS
from posit_bakery.models.manifest.document import ManifestDocument
from posit_bakery.templating.default import create_image_templates


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
            meta_ver: ImageMetadata = deepcopy(meta)
            meta_ver.version = version
            meta_ver.context = context / version
            meta_ver.labels.posit["version"] = version

            versions.append(
                ImageVersion.load(
                    meta=meta_ver,
                    build=build,
                    targets=manifest.target,
                )
            )

        return cls(name=manifest.image_name, context=context, versions=versions)

    @classmethod
    def create(cls, project_context: Path, name: str, base_tag: str):
        context: Path = project_context / name
        create_image_templates(context=context, image_name=name, base_tag=base_tag)

    def create_version(self, manifest: ManifestDocument, version: str, mark_latest: bool):
        ImageVersion.create(
            image_context=self.context,
            version=version,
            targets=manifest.target.keys(),
            mark_latest=mark_latest,
        )

        # Get list of OS from the rendered files
        version_context = self.context / version
        os_list: List[BuildOS] = guess_os_list(version_context)

    @property
    def variants(self) -> List[ImageVariant]:
        return [variant for version in self.versions for variant in version.variants]
