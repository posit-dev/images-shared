import re
from datetime import datetime, timezone
from typing import Dict, List

from pydantic import BaseModel

from posit_bakery.models.config.document import ConfigDocument
from posit_bakery.models.config.repository import ConfigRepository
from posit_bakery.models.project.image import Image, ImageLabels, ImageVariant, Images
from posit_bakery.templating.filters import condense


def target_uid(name: str, version: str, variant: ImageVariant) -> str:
    return re.sub("[.+/]", "-", f"{name}-{version}-{condense(variant.os)}-{variant.target}")


def config_labels(created: str, repository: ConfigRepository) -> Dict[str, str]:
    labels: Dict[str, str] = {
        "created": created,
        "vendor": repository.vendor,
        "maintainer": repository.maintainer,
        "revision": "",  # TODO: Come back to get the commit hash
        "authors": ", ".join(repository.authors),
        "source": repository.url,
    }

    return labels


def image_labels(image_labels: ImageLabels, oci_labels: Dict[str, str]) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    labels.update({f"{image_labels.posit_prefix}.{k}": v for k, v in image_labels.posit.items()})
    labels.update({f"{image_labels.oci_prefix}.{k}": v for k, v in image_labels.oci.items()})
    labels.update({f"{image_labels.oci_prefix}.{k}": v for k, v in oci_labels.items()})

    return labels


class BakeGroup(BaseModel):
    targets: List[str] = []


class BakeTarget(BaseModel):
    context: str
    dockerfile: str
    labels: Dict[str, str]
    tags: List[str]


class BakePlan(BaseModel):
    group: Dict[str, BakeGroup]
    target: Dict[str, BakeTarget]

    @staticmethod
    def update_groups(groups: Dict[str, BakeGroup], uid: str, name: str, target: str):
        groups["default"].targets.append(uid)

        if name not in groups:
            groups[name] = BakeGroup(targets=[])
        groups[name].targets.append(uid)

        if target not in groups:
            groups[target] = BakeGroup(targets=[])
        groups[target].targets.append(uid)

        return groups

    @classmethod
    def create(cls, config: ConfigDocument, images: List[Image]) -> "BakePlan":
        created: str = datetime.now(timezone.utc).isoformat()
        oci_labels: Dict[str, str] = config_labels(repository=config.repository, created=created)
        groups: Dict[str, BakeGroup] = {
            "default": BakeGroup(targets=[]),
        }
        targets: Dict[str, BakeTarget] = {}

        for image in images:
            for version in image.versions:
                for variant in version.variants:
                    uid: str = target_uid(name=image.name, version=version.version, variant=variant)
                    groups = cls.update_groups(groups=groups, uid=uid, name=image.name, target=variant.target)
                    targets[uid] = BakeTarget(
                        # Context is the root of the project; containerfile is relative to context
                        context=".",
                        dockerfile=str(variant.containerfile.relative_to(version.context.parent.parent)),
                        labels=image_labels(image_labels=variant.labels, oci_labels=oci_labels),
                        tags=[
                            f"{reg.base_url}/{image.name}:{tag}" for reg in config.registries for tag in variant.tags
                        ],
                    )

        return cls(group=groups, target=targets)
