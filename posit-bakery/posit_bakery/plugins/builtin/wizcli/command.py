import re
from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, Field, computed_field, model_validator

from posit_bakery.config.dependencies.version import strip_patch
from posit_bakery.config.image.posit_product.const import ReleaseChannelEnum
from posit_bakery.image.image_target import ImageTarget, ImageTargetContext
from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions
from posit_bakery.settings import SETTINGS
from posit_bakery.util import find_bin


def find_wizcli_bin(context: ImageTargetContext) -> str | None:
    """Find the path to the wizcli binary."""
    return find_bin(context.base_path, "wizcli", "WIZCLI_PATH") or "wizcli"


class WizCLICommand(BaseModel):
    image_target: ImageTarget
    wizcli_bin: Annotated[str, Field(default_factory=lambda data: find_wizcli_bin(data["image_target"].context))]
    results_file: Path

    # ToolOptions fields
    tool_options: Annotated[WizCLIOptions | None, Field(default=None)]

    # CLI pass-through options
    disabled_scanners: Annotated[str | None, Field(default=None)]
    driver: Annotated[str, Field(default="extract")]
    policies: Annotated[str | None, Field(default=None)]
    projects: Annotated[str | None, Field(default=None)]
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
        driver: str = "extract",
        policies: str | None = None,
        projects: str | None = None,
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
            policies=policies,
            projects=projects,
            client_id=client_id,
            client_secret=client_secret,
            use_device_code=use_device_code,
            no_browser=no_browser,
            timeout=timeout,
            no_publish=no_publish,
            scan_context_id=scan_context_id,
            log_file=log_file,
        )

    @computed_field
    @property
    def default_scan_context_id(self) -> str:
        """Generate the default scan context ID for grouping related scans in Wiz.

        Dev builds use a per-channel ID (e.g. ``connect-daily``) so each channel
        always reflects the current state. Release and matrix builds use a
        month/minor-stripped version (e.g. ``connect-2026-07``,
        ``connect-content-r4-5-python3-14``) so patch bumps and build-number
        increments update the context in-place rather than creating new ones.
        Positron build-number suffixes (e.g. ``-2`` in ``2026.08.1-2``) are
        stripped after strip_patch so the context stays at monthly granularity.
        """
        t = self.image_target
        if t.release_channel != ReleaseChannelEnum.RELEASE:
            raw = f"{t.image_name}-{t.release_channel.value}"
        else:
            stripped = re.sub(r"-\d+$", "", strip_patch(t.image_version.name))
            raw = f"{t.image_name}-{stripped}"
        return re.sub(r"[ .+/]", "-", raw).lower()

    @computed_field
    @property
    def scan_name(self) -> str:
        """Generate a human-readable scan name for the Wiz UI.

        Follows the same Version-OS-Variant-platform format as bakery's per-platform
        cache tags, so the name maps directly to a real build artifact.
        """
        t = self.image_target
        tv = t.tag_template_values
        suffix = "-".join(part for part in [tv["Version"], tv["OS"], tv["Variant"]] if part)
        return f"{t.image_name}:{suffix}-{SETTINGS.architecture}"

    @computed_field
    @property
    def scan_tags(self) -> list[str]:
        """Generate tags for the Wiz scan from ImageTarget fields.

        Covers every useful grouping axis in the Wiz UI: product, version, channel,
        OS, variant, and platform. User-supplied tool_options.tags are emitted
        separately and can override or extend these.
        """
        t = self.image_target
        tv = t.tag_template_values
        tags = [
            f"product={t.image_name}",
            f"version={t.image_version.name}",
            f"channel={t.release_channel.value}",
            f"platform={SETTINGS.architecture}",
        ]
        if tv["OS"]:
            # "os" is a reserved tag key in Wiz; use "base-os" instead.
            tags.append(f"base-os={tv['OS']}")
        if tv["Variant"]:
            tags.append(f"variant={tv['Variant']}")
        return tags

    @model_validator(mode="after")
    def check_wizcli_bin(self) -> Self:
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

        # Temp-registry images are pushed by digest and carry no tag in the registry, so the
        # tag portion of a `repo:tag@sha256:DIGEST` reference resolves to nothing. Ask for the
        # tag-free form to keep the reference unambiguous regardless of how wizcli parses it.
        cmd.append(self.image_target.ref(digest_only=True))

        # Output file
        cmd.extend(["--json-output-file", str(self.results_file)])

        # Dockerfile
        cmd.extend(["--dockerfile", str(self.image_target.containerfile)])

        # Always set for machine-parseable output
        cmd.extend(["--no-color", "--no-style"])

        # Scan name: Version-OS-Variant-platform, matching the per-platform cache tag format.
        cmd.extend(["--name", self.scan_name])

        # Scan context ID: groups all platform scans of the same image together in Wiz
        # and deduplicates shared findings. Defaults to the image uid (platform-agnostic)
        # so amd64 and arm64 scans of the same image are automatically linked.
        cmd.extend(["--scan-context-id", self.scan_context_id or self.default_scan_context_id])

        # Policies/projects: an explicit CLI value always wins over bakery.yaml,
        # since CI feeds these from secrets and bakery.yaml never should.
        projects = self.projects or (
            ",".join(self.tool_options.projects) if self.tool_options and self.tool_options.projects else None
        )
        if projects:
            cmd.extend(["--projects", projects])

        policies = self.policies or (
            ",".join(self.tool_options.policies) if self.tool_options and self.tool_options.policies else None
        )
        if policies:
            cmd.extend(["--policies", policies])

        # Auto-generated tags from ImageTarget, then user-supplied tool_options.tags.
        for tag in self.scan_tags:
            cmd.extend(["--tags", tag])

        # Remaining ToolOptions fields
        if self.tool_options:
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
        if self.log_file:
            cmd.extend(["--log", self.log_file])

        return cmd
