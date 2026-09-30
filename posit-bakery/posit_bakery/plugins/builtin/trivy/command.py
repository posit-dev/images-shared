from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, Field, computed_field, model_validator

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.trivy.options import TrivyOptions
from posit_bakery.settings import SETTINGS
from posit_bakery.util import find_bin


def find_trivy_bin(base_path: Path) -> str | None:
    """Find the path to the trivy binary."""
    return find_bin(base_path, "trivy", "TRIVY_PATH") or "trivy"


def default_scan_platform() -> str:
    """Platform to scan when the caller does not specify one: the host platform.

    Mirrors ``ImageTarget.ref()``'s own default (and ``WizCLICommand``'s identically-named
    helper) so an unqualified scan still resolves to the artifact built locally.
    """
    return f"linux/{SETTINGS.architecture}"


class TrivyCommand(BaseModel):
    image_target: ImageTarget
    trivy_bin: Annotated[
        str, Field(default_factory=lambda data: find_trivy_bin(data["image_target"].context.base_path))
    ]
    results_file: Path
    platform: Annotated[
        str,
        Field(
            default_factory=default_scan_platform,
            description="Build platform to scan, e.g. 'linux/arm64'. Selects which build metadata digest is scanned.",
        ),
    ]

    # ToolOptions fields
    tool_options: Annotated[TrivyOptions | None, Field(default=None)]

    # CLI pass-through options. Each is post-split by the CLI layer (comma-separated strings
    # become lists before this model ever sees them) and wins over `tool_options` when set,
    # matching WizCLICommand's policies/projects precedence.
    severity: Annotated[list[str] | None, Field(default=None)]
    ignore_unfixed: Annotated[bool | None, Field(default=None)]
    skip_files: Annotated[list[str] | None, Field(default=None)]
    skip_dirs: Annotated[list[str] | None, Field(default=None)]
    exit_code: Annotated[int | None, Field(default=None)]
    scanners: Annotated[list[str] | None, Field(default=None)]
    timeout: Annotated[str | None, Field(default=None)]
    failure_severity: Annotated[list[str] | None, Field(default=None)]

    @classmethod
    def from_image_target(
        cls,
        image_target: ImageTarget,
        results_dir: Path,
        *,
        tool_options: TrivyOptions | None = None,
        platform: str | None = None,
        severity: list[str] | None = None,
        ignore_unfixed: bool | None = None,
        skip_files: list[str] | None = None,
        skip_dirs: list[str] | None = None,
        exit_code: int | None = None,
        scanners: list[str] | None = None,
        timeout: str | None = None,
        failure_severity: list[str] | None = None,
    ) -> "TrivyCommand":
        # Resolve tool options from variant (or, for variant-less images, the parent Image)
        # config if not explicitly provided
        if tool_options is None:
            tool_options = image_target.get_tool_option("trivy")

        image_subdir = results_dir / image_target.image_name
        results_file = image_subdir / f"{image_target.uid}.sarif"

        return cls(
            image_target=image_target,
            results_file=results_file,
            platform=platform or default_scan_platform(),
            tool_options=tool_options,
            severity=severity,
            ignore_unfixed=ignore_unfixed,
            skip_files=skip_files,
            skip_dirs=skip_dirs,
            exit_code=exit_code,
            scanners=scanners,
            timeout=timeout,
            failure_severity=failure_severity,
        )

    @model_validator(mode="after")
    def check_trivy_bin(self) -> Self:
        if not self.trivy_bin:
            raise ValueError(
                "trivy binary path must be specified with the `TRIVY_PATH` environment variable if it cannot be "
                "discovered in the system PATH."
            )
        return self

    @model_validator(mode="after")
    def check_failure_severity_is_scanned(self) -> Self:
        """failureSeverity is read from trivy's SARIF, which trivy filters by `--severity`.

        A gate severity outside the scanned set could never breach, so reject it up front.
        Skipped when no severity is resolved: trivy then scans every severity.
        """
        failure = self.resolved_failure_severity
        scanned = (
            self.severity if self.severity is not None else (self.tool_options.severity if self.tool_options else None)
        )
        if not failure or not scanned:
            return self
        unscanned = sorted({s.strip().upper() for s in failure} - {s.strip().upper() for s in scanned})
        if unscanned:
            raise ValueError(
                f"failureSeverity {unscanned} is not in the scanned severities {list(scanned)}; "
                "trivy only reports scanned severities, so it could never fail the build."
            )
        return self

    @property
    def resolved_failure_severity(self) -> list[str] | None:
        """Resolve the failure-severity threshold used by TrivySuite to compute breach status.

        Not part of trivy's own argv: trivy has no native flag to decouple "what's scanned/
        reported" from "what fails the build". Same CLI-passthrough-wins-over-tool_options
        precedence as every other field here.
        """
        return (
            self.failure_severity
            if self.failure_severity is not None
            else (self.tool_options.failureSeverity if self.tool_options else None)
        )

    @computed_field
    @property
    def command(self) -> list[str]:
        cmd = [self.trivy_bin, "image", "--format", "sarif", "--output", str(self.results_file)]

        # CLI-passthrough options win over bakery.yaml tool_options per field: CI feeds these
        # from workflow inputs/secrets, bakery.yaml never should override an explicit CLI value.
        severity = (
            self.severity if self.severity is not None else (self.tool_options.severity if self.tool_options else None)
        )
        if severity:
            cmd.extend(["--severity", ",".join(severity)])

        ignore_unfixed = (
            self.ignore_unfixed
            if self.ignore_unfixed is not None
            else (self.tool_options.ignoreUnfixed if self.tool_options else None)
        )
        if ignore_unfixed:
            cmd.append("--ignore-unfixed")

        skip_files = (
            self.skip_files
            if self.skip_files is not None
            else (self.tool_options.skipFiles if self.tool_options else None)
        )
        if skip_files:
            for skip_file in skip_files:
                cmd.extend(["--skip-files", skip_file])

        skip_dirs = (
            self.skip_dirs
            if self.skip_dirs is not None
            else (self.tool_options.skipDirs if self.tool_options else None)
        )
        if skip_dirs:
            for skip_dir in skip_dirs:
                cmd.extend(["--skip-dirs", skip_dir])

        exit_code = (
            self.exit_code
            if self.exit_code is not None
            else (self.tool_options.exitCode if self.tool_options else None)
        )
        if exit_code is not None:
            cmd.extend(["--exit-code", str(exit_code)])

        scanners = (
            self.scanners if self.scanners is not None else (self.tool_options.scanners if self.tool_options else None)
        )
        if scanners:
            cmd.extend(["--scanners", ",".join(scanners)])

        timeout = (
            self.timeout if self.timeout is not None else (self.tool_options.timeout if self.tool_options else None)
        )
        if timeout:
            cmd.extend(["--timeout", timeout])

        # Scan the digest built for the requested platform, not the host's: on a
        # cross-platform scan the host digest is absent and ref() would degrade to a
        # mutable registry tag, pointing trivy at an artifact we did not just build.
        # Temp-registry images are pushed by digest and carry no tag in the registry, so the
        # tag portion of a `repo:tag@sha256:DIGEST` reference resolves to nothing. Ask for the
        # tag-free form to keep the reference unambiguous regardless of how trivy parses it.
        cmd.append(self.image_target.ref(platform=self.platform, digest_only=True))

        return cmd
