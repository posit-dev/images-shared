import re
from pathlib import Path
from typing import Dict, List, Annotated

import python_on_whales
from pydantic import BaseModel, Field, computed_field

from posit_bakery.image.image_target import ImageTarget


class BakeGroup(BaseModel):
    targets: List[str] = []


class BakeTarget(BaseModel):
    image_name: Annotated[str, Field(exclude=True)]
    image_version: Annotated[str, Field(exclude=True)]
    image_variant: Annotated[str | None, Field(default=None, exclude=True)]
    image_os: Annotated[str | None, Field(default=None, exclude=True)]

    context: Annotated[str, Field(default=".")]
    dockerfile: str
    labels: Dict[str, str]
    tags: List[str]

    @classmethod
    def from_image_target(cls, image_target: ImageTarget) -> "BakeTarget":
        return cls(
            image_name=image_target.image_name,
            image_version=image_target.image_version.name,
            image_variant=image_target.image_variant.name if image_target.image_variant else None,
            image_os=image_target.image_os.name if image_target.image_os else None,
            dockerfile=image_target.containerfile,
            labels=image_target.labels,
            tags=image_target.tags,
        )


class BakePlan(BaseModel):
    context: Annotated[Path, Field(exclude=True)]
    group: Dict[str, BakeGroup]
    target: Dict[str, BakeTarget]

    @computed_field
    @property
    def bake_file(self) -> Path:
        """Return the path to the bake file in the context directory."""
        return self.context / ".bakery-bake.json"

    @staticmethod
    def update_groups(
        groups: Dict[str, BakeGroup], uid: str, image_name: str, image_variant: str
    ) -> Dict[str, BakeGroup]:
        groups["default"].targets.append(uid)

        if image_name not in groups:
            groups[image_name] = BakeGroup(targets=[])
        groups[image_name].targets.append(uid)

        if image_variant not in groups:
            groups[image_variant] = BakeGroup(targets=[])
        groups[image_variant].targets.append(uid)

        return groups

    @classmethod
    def from_image_targets(cls, context: Path, image_targets: List[ImageTarget]) -> "BakePlan":
        groups: Dict[str, BakeGroup] = {
            "default": BakeGroup(targets=[]),
        }
        targets: Dict[str, BakeTarget] = {}

        for image_target in image_targets:
            bake_target = BakeTarget.from_image_target(image_target)
            groups = cls.update_groups(
                groups=groups,
                uid=image_target.uid,
                image_name=bake_target.image_name,
                image_variant=bake_target.image_variant,
            )

            targets[image_target.uid] = bake_target

        return cls(context=context, group=groups, target=targets)

    def write(self):
        """Write the bake plan to a file in the context directory."""
        with open(self.bake_file, "w") as f:
            f.write(self.model_dump_json(indent=2))

    def remove(self):
        """Delete the bake plan file if it exists."""
        self.bake_file.unlink(missing_ok=True)

    def build(self, load: bool = True, push: bool = False, cache: bool = True):
        """Run the bake plan to build all targets."""
        self.write()
        python_on_whales.docker.bake(
            files=[self.bake_file.name],
            load=load,
            push=push,
            cache=cache,
        )
        self.remove()
