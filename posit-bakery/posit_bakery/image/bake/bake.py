import os
from pathlib import Path
from typing import Annotated

import python_on_whales
from pydantic import BaseModel, Field, field_serializer

from posit_bakery.image.image_target import ImageTarget


class BakeGroup(BaseModel):
    """Represents a group of targets in a Docker Bake plan."""

    targets: Annotated[list[str], Field(default_factory=list, description="List of target UIDs in this group.")]


class BakeTarget(BaseModel):
    """Represents a target for building a Docker image in a Docker Bake plan."""

    image_name: Annotated[
        str, Field(exclude=True, description="Name of the image.", examples=["package-manager", "workbench"])
    ]
    image_version: Annotated[str, Field(exclude=True, description="Version of the image.", examples=["1.0.0"])]
    image_variant: Annotated[
        str | None,
        Field(default=None, exclude=True, description="Variant of the image.", examples=["Standard", "Minimal"]),
    ]
    image_os: Annotated[
        str | None,
        Field(
            default=None,
            exclude=True,
            description="Operating system of the image.",
            examples=["Ubuntu 22.04", "Rocky 11"],
        ),
    ]

    context: Annotated[
        Path | str,
        Field(
            default=".",
            description="Path to the build context path relative to the plan's context path. Typically this is the "
            "current working directory or '.'.",
        ),
    ]
    dockerfile: Annotated[Path | str, Field(description="Path to the Containerfile relative to the context.")]
    labels: Annotated[dict[str, str], Field(description="Labels to apply to the image.")]
    tags: Annotated[list[str], Field(description="Tags to apply to the image.")]

    @field_serializer("dockerfile", "context", when_used="json")
    @staticmethod
    def serialize_path(value: Path | str) -> str:
        """Serialize Path or str to a string for JSON output.

        :param value: The Path or str to serialize.

        :return: The string representation of the path.
        """
        return str(value)

    @classmethod
    def from_image_target(cls, image_target: ImageTarget) -> "BakeTarget":
        """Create a BakeTarget from an ImageTarget."""
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
    """Represents a JSON bake plan for building Docker images using Docker Bake."""

    context: Annotated[Path, Field(exclude=True, description="Absolute path to the build context directory.")]
    group: Annotated[dict[str, BakeGroup], Field(description="Groups of targets for the bake plan.")]
    target: Annotated[dict[str, BakeTarget], Field(description="Targets in the bake plan.")]

    @property
    def bake_file(self) -> Path:
        """Return the path to the bake file in the context directory."""
        return (self.context / ".bakery-bake.json").resolve()

    @staticmethod
    def update_groups(
        groups: dict[str, BakeGroup], uid: str, image_name: str, image_variant: str
    ) -> dict[str, BakeGroup]:
        """Update the default, image name, and image variant groups with the given UID.

        :param groups: The current groups of targets.
        :param uid: The unique identifier for the target.
        :param image_name: The name of the image.
        :param image_variant: The variant of the image.

        :return: The updated groups with the new target added.
        """
        groups["default"].targets.append(uid)

        if image_name not in groups:
            groups[image_name] = BakeGroup(targets=[])
        groups[image_name].targets.append(uid)

        if image_variant is not None:
            if image_variant not in groups:
                groups[image_variant] = BakeGroup(targets=[])
            groups[image_variant].targets.append(uid)

        return groups

    @classmethod
    def from_image_targets(cls, context: Path, image_targets: list[ImageTarget]) -> "BakePlan":
        """Create a BakePlan from a list of ImageTarget objects.

        :param context: The absolute path to the build context directory.
        :param image_targets: A list of ImageTarget objects to include in the bake plan.

        :return: A BakePlan object containing the context, groups, and targets.
        """
        groups: dict[str, BakeGroup] = {
            "default": BakeGroup(targets=[]),
        }
        targets: dict[str, BakeTarget] = {}

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
            f.write(self.model_dump_json(indent=2, exclude_none=True))

    def remove(self):
        """Delete the bake plan file if it exists."""
        self.bake_file.unlink(missing_ok=True)

    def build(self, load: bool = True, push: bool = False, cache: bool = True, clean_bakefile: bool = True):
        """Run the bake plan to build all targets."""
        original_cwd = os.getcwd()
        os.chdir(self.context)

        self.write()
        python_on_whales.docker.buildx.bake(
            files=[self.bake_file.name],
            load=load,
            push=push,
            cache=cache,
            set={"*.platform": "linux/amd64"},
        )
        if clean_bakefile:
            self.remove()

        os.chdir(original_cwd)
