from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, Field, computed_field, model_validator

from posit_bakery.image.image_target import ImageTarget, ImageTargetContext
from posit_bakery.plugins.builtin.trivy.options import TrivyOptions
from posit_bakery.util import find_bin

TRIVY_ALL_SCANNERS = ["vuln", "secret", "license", "misconfig"]
# Trivy's own default for `trivy image` only runs vuln,secret -- license/misconfig
# are off by default. The --disabled-scanners complement must be computed against
# this default set, not TRIVY_ALL_SCANNERS, or disabling e.g. just "secret" would
# silently turn ON license/misconfig scanning (which report real severities and
# pollute the vulnerability count with unrelated findings).
TRIVY_DEFAULT_SCANNERS = ["vuln", "secret"]


def find_trivy_bin(context: ImageTargetContext) -> str | None:
    """Find the path to the trivy binary."""
    return find_bin(context.base_path, "trivy", "TRIVY_PATH") or "trivy"


def discover_trivy_config(image_target: ImageTarget) -> Path | None:
    """Look for a native `trivy.yaml` at the image's root directory (e.g. `workbench/trivy.yaml`)."""
    candidate = image_target.context.base_path / image_target.image_name / "trivy.yaml"
    return candidate if candidate.is_file() else None


class TrivyCommand(BaseModel):
    image_target: ImageTarget
    trivy_bin: Annotated[str, Field(default_factory=lambda data: find_trivy_bin(data["image_target"].context))]
    results_file: Path

    # ToolOptions fields
    tool_options: Annotated[TrivyOptions | None, Field(default=None)]

    # CLI pass-through options
    severity: Annotated[str | None, Field(default=None)]
    disabled_scanners: Annotated[str | None, Field(default=None)]
    timeout: Annotated[str | None, Field(default=None)]
    trivy_config: Annotated[Path | None, Field(default=None)]

    @classmethod
    def from_image_target(
        cls,
        image_target: ImageTarget,
        results_dir: Path,
        *,
        tool_options: TrivyOptions | None = None,
        severity: str | None = None,
        disabled_scanners: str | None = None,
        timeout: str | None = None,
        trivy_config: Path | None = None,
    ) -> "TrivyCommand":
        # Resolve tool options from variant config if not explicitly provided
        if tool_options is None and image_target.image_variant:
            tool_options = image_target.image_variant.get_tool_option("trivy")

        if trivy_config is None:
            trivy_config = discover_trivy_config(image_target)

        image_subdir = results_dir / image_target.image_name
        results_file = image_subdir / f"{image_target.uid}.sarif"

        return cls(
            image_target=image_target,
            results_file=results_file,
            tool_options=tool_options,
            severity=severity,
            disabled_scanners=disabled_scanners,
            timeout=timeout,
            trivy_config=trivy_config,
        )

    @model_validator(mode="after")
    def check_trivy_bin(self) -> Self:
        if not self.trivy_bin:
            raise ValueError(
                "trivy binary path must be specified with the `TRIVY_PATH` environment variable if it cannot be "
                "discovered in the system PATH."
            )
        return self

    @computed_field
    @property
    def command(self) -> list[str]:
        cmd = [self.trivy_bin, "image", self.image_target.ref()]

        cmd.extend(["--format", "sarif"])
        cmd.extend(["--output", str(self.results_file)])
        cmd.append("--quiet")

        severity = self.severity or (
            ",".join(self.tool_options.severity) if self.tool_options and self.tool_options.severity else None
        )
        if severity:
            cmd.extend(["--severity", severity])

        disabled_scanners = self.disabled_scanners or (
            ",".join(self.tool_options.disabledScanners)
            if self.tool_options and self.tool_options.disabledScanners
            else None
        )
        if disabled_scanners:
            disabled_set = {s.strip() for s in disabled_scanners.split(",") if s.strip()}
            enabled = [s for s in TRIVY_DEFAULT_SCANNERS if s not in disabled_set]
            cmd.extend(["--scanners", ",".join(enabled)])

        timeout = self.timeout or (self.tool_options.timeout if self.tool_options else None)
        if timeout:
            cmd.extend(["--timeout", timeout])

        if self.trivy_config:
            cmd.extend(["--config", str(self.trivy_config)])

        return cmd
