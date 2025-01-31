import re
from datetime import datetime, timezone
from typing import Dict, List

from pydantic import BaseModel

from posit_bakery.models.image.image import Image
from posit_bakery.models.image.variant import ImageVariant
from posit_bakery.templating.filters import condense


def target_uid(name: str, version: str, variant: ImageVariant) -> str:
    return re.sub("[.+/]", "-", f"{name}-{version}-{condense(variant.os)}-{variant.target}")


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
    def create(cls, images: List[Image]) -> "BakePlan":
        created: str = datetime.now(timezone.utc).isoformat()
        groups: Dict[str, BakeGroup] = {
            "default": BakeGroup(targets=[]),
        }
        targets: Dict[str, BakeTarget] = {}

        for image in images:
            for version in image.versions:
                for variant in version.variants:
                    uid: str = target_uid(name=image.name, version=version.version, variant=variant)
                    groups = cls.update_groups(groups=groups, uid=uid, name=image.name, target=variant.target)

                    labels: Dict[str, str] = {
                        "org.opencontainers.image.created": created,
                    }
                    labels.update(variant.labels)

                    targets[uid] = BakeTarget(
                        # Context is the root of the project; containerfile is relative to context
                        context=".",
                        dockerfile=str(variant.containerfile.relative_to(version.context.parent.parent)),
                        labels=labels,
                        tags=variant.tags,
                    )

        return cls(group=groups, target=targets)
