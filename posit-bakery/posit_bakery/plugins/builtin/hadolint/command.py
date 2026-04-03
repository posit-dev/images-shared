import logging
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, computed_field

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.hadolint.options import HadolintOptions
from posit_bakery.settings import SETTINGS
from posit_bakery.util import find_bin


def find_hadolint_bin(base_path: Path) -> str:
    """Find the path to the hadolint binary."""
    return find_bin(base_path, "hadolint", "HADOLINT_PATH") or "hadolint"


class HadolintCommand(BaseModel):
    image_target: ImageTarget
    hadolint_bin: Annotated[str, Field()]
    containerfile_path: Annotated[Path, Field(description="Absolute path to the Containerfile.")]
    options: Annotated[HadolintOptions, Field(default_factory=HadolintOptions)]

    @classmethod
    def from_image_target(
        cls,
        image_target: ImageTarget,
        options_override: HadolintOptions | None = None,
    ) -> "HadolintCommand":
        hadolint_bin = find_hadolint_bin(image_target.context.base_path)
        containerfile_path = image_target.context.base_path / image_target.containerfile

        # Load options from variant, then merge with override
        variant_options = None
        if image_target.image_variant:
            variant_options = image_target.image_variant.get_tool_option("hadolint")

        if options_override and variant_options:
            options = options_override.update(variant_options)
        elif options_override:
            options = options_override
        elif variant_options:
            options = variant_options
        else:
            options = HadolintOptions()

        # Apply default failure threshold if no source provided one
        if options.failureThreshold is None:
            options = options.model_copy(update={"failureThreshold": "error"})

        return cls(
            image_target=image_target,
            hadolint_bin=hadolint_bin,
            containerfile_path=containerfile_path,
            options=options,
        )

    @computed_field
    @property
    def command(self) -> list[str]:
        """Return the full hadolint command to run."""
        cmd = [self.hadolint_bin, "--format", "json"]

        if SETTINGS.log_level == logging.DEBUG:
            cmd.append("--verbose")

        if self.options.failureThreshold is not None:
            cmd.extend(["--failure-threshold", self.options.failureThreshold])

        if self.options.ignored:
            for rule in self.options.ignored:
                cmd.extend(["--ignore", rule])

        if self.options.labelSchema:
            for label, schema_type in self.options.labelSchema.items():
                cmd.extend(["--require-label", f"{label}:{schema_type}"])

        if self.options.noFail is True:
            cmd.append("--no-fail")

        if self.options.override:
            for level in ("error", "warning", "info", "style"):
                rules = getattr(self.options.override, level, None)
                if rules:
                    for rule in rules:
                        cmd.extend([f"--{level}", rule])

        if self.options.strictLabels is True:
            cmd.append("--strict-labels")

        if self.options.disableIgnorePragma is True:
            cmd.append("--disable-ignore-pragma")

        if self.options.trustedRegistries:
            for registry in self.options.trustedRegistries:
                cmd.extend(["--trusted-registry", registry])

        cmd.append(str(self.containerfile_path))
        return cmd
