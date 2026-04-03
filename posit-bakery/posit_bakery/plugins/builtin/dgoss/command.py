import re
from pathlib import Path
from typing import Annotated, Self, Literal

from pydantic import BaseModel, Field, model_validator, computed_field

from posit_bakery.image.image_target import ImageTargetContext, ImageTarget
from posit_bakery.util import find_bin


def find_dgoss_bin(context: ImageTargetContext) -> str | None:
    """Find the path to the DGoss binary for the given image target's context.

    :param context: The context of the image target to search for the DGoss binary.
    """
    return find_bin(context.base_path, "dgoss", "DGOSS_PATH") or "dgoss"


def find_goss_bin(context: ImageTargetContext) -> str | None:
    """Find the path to the Goss binary for the given image target's context.

    :param context: The context of the image target to search for the Goss binary.
    """
    return find_bin(context.base_path, "goss", "GOSS_PATH")


def find_test_path(context: ImageTargetContext) -> Path | None:
    """Find the path to the Goss test directory for the given image target's context."""
    # Check for tests in the version path first
    tests_path = context.version_path / "test"
    if tests_path.exists():
        return tests_path

    # If not found, check in the image path
    tests_path = context.image_path / "test"
    if tests_path.exists():
        return tests_path

    # If not found, return None to indicate no tests found
    return None


class DGossCommand(BaseModel):
    image_target: ImageTarget
    dgoss_bin: Annotated[str, Field(default_factory=lambda data: find_dgoss_bin(data["image_target"].context))]
    goss_bin: Annotated[str | None, Field(default_factory=lambda data: find_goss_bin(data["image_target"].context))]
    dgoss_command: Annotated[str, Field(default="run")]
    version_mountpoint: Literal["/tmp/version"] = "/tmp/version"
    image_mountpoint: Literal["/tmp/image"] = "/tmp/image"
    project_mountpoint: Literal["/tmp/project"] = "/tmp/project"

    platform: Annotated[str | None, Field(default=None, description="The platform to target for container execution.")]
    test_path: Annotated[Path | None, Field(default_factory=lambda data: find_test_path(data["image_target"].context))]
    runtime_options: Annotated[str | None, Field(default=None, description="Additional runtime options for dgoss.")]
    wait: Annotated[int, Field(default=0)]
    image_command: Annotated[str, Field(default="sleep infinity")]

    @property
    def dgoss_environment(self) -> dict[str, str]:
        """Return the environment variables for the DGoss command."""
        env = {
            "GOSS_FILES_PATH": str(self.test_path),
            "GOSS_OPTS": "--format json --no-color",
        }
        if self.goss_bin:
            env["GOSS_PATH"] = self.goss_bin
        if self.wait > 0:
            env["GOSS_SLEEP"] = str(self.wait)
        return env

    @property
    def image_environment(self) -> dict[str, str]:
        """Return the environment variables for the DGoss command."""
        e = {
            "IMAGE_VERSION": self.image_target.image_version.name,
            "IMAGE_VERSION_MOUNT": str(self.version_mountpoint),
            "IMAGE_MOUNT": str(self.image_mountpoint),
            "PROJECT_MOUNT": str(self.project_mountpoint),
        }
        if self.image_target.image_variant:
            e["IMAGE_VARIANT"] = self.image_target.image_variant.name
        if self.image_target.image_os:
            e["IMAGE_OS"] = self.image_target.image_os.name
            e["IMAGE_OS_NAME"] = self.image_target.image_os.buildOS.name
            e["IMAGE_OS_CODENAME"] = self.image_target.image_os.buildOS.codename or ""
            e["IMAGE_OS_FAMILY"] = self.image_target.image_os.buildOS.family.value
            e["IMAGE_OS_VERSION"] = self.image_target.image_os.buildOS.version
        if self.platform:
            e["IMAGE_OS_PLATFORM"] = self.platform
        if self.image_target.build_args:
            for arg, value in self.image_target.build_args.items():
                env_var = f"BUILD_ARG_{arg.upper()}"
                e[env_var] = value

        return e

    @property
    def volume_mounts(self) -> list[tuple[str, str]]:
        return [
            (str(self.image_target.context.version_path.resolve()), str(self.version_mountpoint)),
            (str(self.image_target.context.image_path.resolve()), str(self.image_mountpoint)),
            (str(self.image_target.context.base_path.resolve()), str(self.project_mountpoint)),
        ]

    @classmethod
    def from_image_target(cls, image_target: ImageTarget, platform: str | None = None) -> "DGossCommand":
        args = {
            "image_target": image_target,
        }
        if platform:
            args["platform"] = platform
        if image_target.image_variant:
            goss_options = image_target.image_variant.get_tool_option("goss")
            if goss_options is not None:
                args["runtime_options"] = goss_options.runtimeOptions
                args["image_command"] = goss_options.command
                args["wait"] = goss_options.wait
        return cls(**args)

    @model_validator(mode="after")
    def validate(self) -> Self:
        """Validate the DGoss command configuration."""
        if not self.dgoss_bin:
            raise ValueError(
                "dgoss binary path must be specified with the `DGOSS_PATH` environment variable if it cannot be "
                "discovered in the system PATH."
            )
        if not self.test_path:
            raise ValueError(
                f"No test directory was found for target '{str(self.image_target)}'. Ensure the test directory "
                f"and test/goss.yaml file exist in either the version path or image path."
            )
        return self

    @computed_field
    @property
    def command(self) -> list[str]:
        """Return the full DGoss command to run."""
        cmd = [self.dgoss_bin, self.dgoss_command]

        if self.platform:
            cmd.extend(["--platform", self.platform])
        for mount in self.volume_mounts:
            cmd.extend(["-v", f"{mount[0]}:{mount[1]}"])
        for env_var, value in self.image_environment.items():
            if value is not None:
                env_value = re.sub(r"([\"\'\\$`!*?&#()|<>;\[\]{}\s])", r"\\\1", value)
                cmd.extend(["-e", f"{env_var}={env_value}"])
        cmd.append("--init")
        if self.runtime_options:
            # TODO: We may want to validate this to ensure options are not duplicated.
            cmd.extend(self.runtime_options.split())
        if self.platform:
            cmd.append(self.image_target.ref(self.platform))
        else:
            cmd.append(self.image_target.ref())
        cmd.extend(self.image_command.split())

        return cmd
