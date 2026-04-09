from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, Field, computed_field, model_validator

from posit_bakery.image.image_target import ImageTarget, ImageTargetContext
from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions
from posit_bakery.util import find_bin


def find_wizcli_bin(context: ImageTargetContext) -> str | None:
    """Find the path to the wizcli binary."""
    return find_bin(context.base_path, "wizcli", "WIZCLI_PATH") or "wizcli"


def find_wiz_config_file(context: ImageTargetContext) -> Path | None:
    """Find a .wiz configuration file, checking version path then image path."""
    version_wiz = context.version_path / ".wiz"
    if version_wiz.exists():
        return version_wiz

    image_wiz = context.image_path / ".wiz"
    if image_wiz.exists():
        return image_wiz

    return None


class WizCLICommand(BaseModel):
    image_target: ImageTarget
    wizcli_bin: Annotated[str, Field(default_factory=lambda data: find_wizcli_bin(data["image_target"].context))]
    results_file: Path
    wiz_config_file: Annotated[
        Path | None, Field(default_factory=lambda data: find_wiz_config_file(data["image_target"].context))
    ]

    # ToolOptions fields
    tool_options: Annotated[WizCLIOptions | None, Field(default=None)]

    # CLI pass-through options
    disabled_scanners: Annotated[str | None, Field(default=None)]
    driver: Annotated[str | None, Field(default=None)]
    client_id: Annotated[str | None, Field(default=None)]
    client_secret: Annotated[str | None, Field(default=None)]
    use_device_code: Annotated[bool, Field(default=False)]
    no_browser: Annotated[bool, Field(default=False)]
    timeout: Annotated[str | None, Field(default=None)]
    no_publish: Annotated[bool, Field(default=False)]
    scan_context_id: Annotated[str | None, Field(default=None)]
    log_file: Annotated[str | None, Field(default=None)]

    @classmethod
    def from_image_target(
        cls,
        image_target: ImageTarget,
        results_dir: Path,
        *,
        tool_options: WizCLIOptions | None = None,
        disabled_scanners: str | None = None,
        driver: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        use_device_code: bool = False,
        no_browser: bool = False,
        timeout: str | None = None,
        no_publish: bool = False,
        scan_context_id: str | None = None,
        log_file: str | None = None,
    ) -> "WizCLICommand":
        # Resolve tool options from variant config if not explicitly provided
        if tool_options is None and image_target.image_variant:
            tool_options = image_target.image_variant.get_tool_option("wizcli")

        image_subdir = results_dir / image_target.image_name
        results_file = image_subdir / f"{image_target.uid}.json"

        return cls(
            image_target=image_target,
            results_file=results_file,
            tool_options=tool_options,
            disabled_scanners=disabled_scanners,
            driver=driver,
            client_id=client_id,
            client_secret=client_secret,
            use_device_code=use_device_code,
            no_browser=no_browser,
            timeout=timeout,
            no_publish=no_publish,
            scan_context_id=scan_context_id,
            log_file=log_file,
        )

    @model_validator(mode="after")
    def validate(self) -> Self:
        if not self.wizcli_bin:
            raise ValueError(
                "wizcli binary path must be specified with the `WIZCLI_PATH` environment variable if it cannot be "
                "discovered in the system PATH."
            )
        return self

    @computed_field
    @property
    def command(self) -> list[str]:
        cmd = [self.wizcli_bin, "scan", "container-image"]

        # Image reference
        cmd.append(self.image_target.ref())

        # Output file
        cmd.extend(["--json-output-file", str(self.results_file)])

        # Dockerfile
        cmd.extend(["--dockerfile", str(self.image_target.containerfile)])

        # Wiz configuration file (only if found at version or image level)
        if self.wiz_config_file:
            cmd.extend(["--wiz-configuration-file", str(self.wiz_config_file)])

        # Always set for machine-parseable output
        cmd.extend(["--no-color", "--no-style"])

        # ToolOptions fields
        if self.tool_options:
            if self.tool_options.projects:
                cmd.extend(["--projects", ",".join(self.tool_options.projects)])
            if self.tool_options.policies:
                cmd.extend(["--policies", ",".join(self.tool_options.policies)])
            if self.tool_options.tags:
                for tag in self.tool_options.tags:
                    cmd.extend(["--tags", tag])
            if self.tool_options.scanOsManagedLibraries is not None:
                cmd.append(f"--scan-os-managed-libraries={str(self.tool_options.scanOsManagedLibraries).lower()}")
            if self.tool_options.scanGoStandardLibrary is not None:
                cmd.append(f"--scan-go-standard-library={str(self.tool_options.scanGoStandardLibrary).lower()}")

        # CLI pass-through options
        if self.disabled_scanners:
            cmd.extend(["--disabled-scanners", self.disabled_scanners])
        if self.driver:
            cmd.extend(["--driver", self.driver])
        if self.client_id:
            cmd.extend(["--client-id", self.client_id])
        if self.client_secret:
            cmd.extend(["--client-secret", self.client_secret])
        if self.use_device_code:
            cmd.append("--use-device-code")
        if self.no_browser:
            cmd.append("--no-browser")
        if self.timeout:
            cmd.extend(["--timeout", self.timeout])
        if self.no_publish:
            cmd.append("--no-publish")
        if self.scan_context_id:
            cmd.extend(["--scan-context-id", self.scan_context_id])
        if self.log_file:
            cmd.extend(["--log", self.log_file])

        return cmd
