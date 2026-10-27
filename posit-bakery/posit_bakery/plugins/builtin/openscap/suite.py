import json
import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.openscap.command import (
    StrategyEnum,
    default_scanner_image,
    ensure_scanner_image,
    extract_command,
    os_release_command,
    reclaim_command,
    resolve_strategy,
    scan_command,
    target_mount_args,
)
from posit_bakery.plugins.builtin.openscap.content import (
    DEFAULT_CONTENT_VERSION,
    container_tailoring,
    datastream_for,
    fetch_file,
    list_profiles,
    parse_os_release,
    product_for,
    resolve_profile,
)
from posit_bakery.plugins.builtin.openscap.errors import (
    OPENSCAP_EXIT_CODE_GATE_BREACH,
    BakeryOpenSCAPContentError,
    BakeryOpenSCAPError,
)
from posit_bakery.plugins.builtin.openscap.options import (
    BUILTIN_CONTAINER_TAILORING,
    DEFAULT_FORMATS,
    DEFAULT_PROFILE,
    NO_TAILORING,
    FailOnEnum,
    OpenSCAPOptions,
    OutputFormatEnum,
)
from posit_bakery.plugins.builtin.openscap.report import OpenSCAPScanNotRun, OpenSCAPScanReport, target_metadata
from posit_bakery.settings import SETTINGS

log = logging.getLogger(__name__)

# oscap xccdf eval: 0 = all rules passed, 2 = at least one rule failed; both mean the evaluation ran.
OSCAP_SCAN_RAN_CODES = (0, 2)


@dataclass
class ResolvedOptions:
    profile: str
    content_version: str
    datastream: str | None
    tailoring: str
    skip_rules: list[str]
    fail_on: FailOnEnum
    formats: list[OutputFormatEnum]


@dataclass
class TargetOutcome:
    target: ImageTarget
    result: OpenSCAPScanReport | OpenSCAPScanNotRun
    status: str  # OK | BREACH | ERROR | SKIPPED
    error: BakeryOpenSCAPError | None = None


def resolve_options(cli: dict, yaml_options: OpenSCAPOptions | None) -> ResolvedOptions:
    """CLI values win over bakery.yaml values, which win over defaults."""
    y = yaml_options or OpenSCAPOptions()

    def pick(cli_key: str, yaml_value, default):
        value = cli.get(cli_key)
        return value if value is not None else (yaml_value if yaml_value is not None else default)

    return ResolvedOptions(
        profile=pick("profile", y.profile, DEFAULT_PROFILE),
        content_version=pick("content_version", y.contentVersion, DEFAULT_CONTENT_VERSION),
        datastream=pick("datastream", y.datastream, None),
        tailoring=pick("tailoring", y.tailoring, BUILTIN_CONTAINER_TAILORING),
        skip_rules=pick("skip_rules", y.skipRules, []),
        fail_on=FailOnEnum(pick("fail_on", y.failOn, FailOnEnum.NONE)),
        formats=pick("formats", y.formats, DEFAULT_FORMATS),
    )


class OpenSCAPSuite:
    def __init__(
        self,
        context: Path,
        image_targets: list[ImageTarget],
        *,
        platform: str | None = None,
        strategy: StrategyEnum = StrategyEnum.AUTO,
        scanner_image: str | None = None,
        timeout: int = 600,
        docker: str = "docker",
        **cli_options,
    ) -> None:
        self.context = context
        self.results_dir = context / "results" / "openscap"
        self.targets = image_targets
        self.platform = platform or f"linux/{SETTINGS.architecture}"
        self.strategy = strategy
        self.scanner_image = scanner_image or default_scanner_image()
        self.timeout = timeout
        self.docker = docker
        self.cli_options = cli_options

    def run(self) -> list[TargetOutcome]:
        # Same as trivy: each run replaces the previous run's results.
        shutil.rmtree(self.results_dir, ignore_errors=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        log.info(f"Preparing OpenSCAP scanner image '{self.scanner_image}'")
        ensure_scanner_image(self.docker, self.scanner_image)
        strategy = resolve_strategy(self.docker, self.strategy)
        log.debug(f"[bright_black]Using '{strategy.value}' scan strategy")

        outcomes = []
        for target in self.targets:
            log.info(f"[bright_blue bold]=== Scanning '{target}' with OpenSCAP ===")
            yaml_options = target.get_tool_option("openscap")
            options = resolve_options(
                self.cli_options, yaml_options if isinstance(yaml_options, OpenSCAPOptions) else None
            )
            try:
                outcome = self._scan_target(target, options, strategy)
            except BakeryOpenSCAPError as e:
                outcome = TargetOutcome(target, OpenSCAPScanNotRun("ERROR", e.message), "ERROR", e)
            except subprocess.TimeoutExpired:
                reason = f"timed out after {self.timeout}s"
                err = BakeryOpenSCAPError(f"OpenSCAP scan of '{target}' {reason}")
                outcome = TargetOutcome(target, OpenSCAPScanNotRun("ERROR", reason), "ERROR", err)
            except (BakeryOpenSCAPContentError, subprocess.SubprocessError, OSError, ValueError) as e:
                err = BakeryOpenSCAPError(f"OpenSCAP scan failed for '{target}': {e}")
                outcome = TargetOutcome(target, OpenSCAPScanNotRun("ERROR", str(e)), "ERROR", err)
            self._write_outputs(outcome, options)
            log.info(f"OpenSCAP status for '{target}': {outcome.status}")
            outcomes.append(outcome)
        return outcomes

    def _name(self) -> str:
        return f"bakery-openscap-{uuid.uuid4().hex[:12]}"

    def _run_container(self, cmd: list[str], name: str, **kwargs) -> subprocess.CompletedProcess:
        """Run a named scanner container, force-removing it if the client is interrupted (e.g. on timeout).

        Killing the docker client does not stop the container, so without this a timed-out scan keeps running.
        """
        try:
            return subprocess.run(cmd, timeout=self.timeout, **kwargs)
        finally:
            subprocess.run([self.docker, "rm", "-f", name], capture_output=True)

    @contextmanager
    def _target_mount(self, ref: str, strategy: StrategyEnum):
        if strategy == StrategyEnum.IMAGE_MOUNT:
            yield target_mount_args(strategy, ref, None)
            return
        volume = self._name()
        container = None
        try:
            subprocess.run([self.docker, "volume", "create", volume], check=True, capture_output=True)
            # The command is never run; it only satisfies `create` for images without CMD/ENTRYPOINT.
            container = subprocess.run(
                [self.docker, "create", ref, "bakery-openscap-noop"], check=True, capture_output=True, text=True
            ).stdout.strip()
            export = subprocess.Popen([self.docker, "export", container], stdout=subprocess.PIPE)
            try:
                name = self._name()
                tar = self._run_container(
                    extract_command(self.docker, self.scanner_image, volume, name),
                    name,
                    stdin=export.stdout,
                    capture_output=True,
                )
            finally:
                if export.stdout:
                    export.stdout.close()
                if export.poll() is None:
                    export.kill()
                export_rc = export.wait()
            # tar accepts an archive truncated at a file boundary, so both ends must succeed or the rootfs is partial.
            if export_rc != 0 or tar.returncode != 0:
                raise BakeryOpenSCAPError(
                    f"Failed to export '{ref}' into a scan volume",
                    stdout=tar.stderr,
                    metadata={"export_exit_code": export_rc, "tar_exit_code": tar.returncode},
                )
            yield target_mount_args(strategy, ref, volume)
        finally:
            if container:
                subprocess.run([self.docker, "rm", "-f", container], capture_output=True)
            subprocess.run([self.docker, "volume", "rm", "-f", volume], capture_output=True)

    @contextmanager
    def _work_dir(self):
        """Temporary output directory that is handed back to the invoking user before deletion."""
        with tempfile.TemporaryDirectory(prefix="bakery-openscap-") as work:
            work_dir = Path(work)
            try:
                yield work_dir
            finally:
                uid = os.getuid()
                if any(f.lstat().st_uid != uid for f in work_dir.rglob("*")):
                    subprocess.run(reclaim_command(self.docker, self.scanner_image, work_dir), capture_output=True)

    def _scan_target(self, target: ImageTarget, options: ResolvedOptions, strategy: StrategyEnum) -> TargetOutcome:
        ref = target.ref(platform=self.platform, digest_only=True)
        p = subprocess.run(
            [self.docker, "image", "inspect", "--format", "{{.Id}}", ref], capture_output=True, text=True
        )
        if p.returncode != 0:
            err = BakeryOpenSCAPError(f"Image '{ref}' for '{target}' is not available locally", stdout=p.stderr)
            return TargetOutcome(target, OpenSCAPScanNotRun("ERROR", "image not found"), "ERROR", err)
        provenance = {"image_ref": ref, "image_id": p.stdout.strip(), "scanner_image": self.scanner_image}

        with self._target_mount(ref, strategy) as mount_args, self._work_dir() as work_dir:
            name = self._name()
            p = self._run_container(
                os_release_command(self.docker, self.scanner_image, mount_args, name),
                name,
                capture_output=True,
                text=True,
            )
            if p.returncode != 0:
                err = BakeryOpenSCAPError(f"Could not read /etc/os-release from '{ref}'", stdout=p.stderr)
                return TargetOutcome(target, OpenSCAPScanNotRun("ERROR", "os-release unreadable"), "ERROR", err)
            os_release = parse_os_release(p.stdout)
            product = product_for(os_release.get("ID", ""), os_release.get("VERSION_ID", ""))
            content = f"ComplianceAsCode {options.content_version}"

            if options.datastream:
                datastream = fetch_file(options.datastream, self.context)
                content = options.datastream
            elif product is None:
                return self._skipped(target, f"unsupported OS '{os_release.get('PRETTY_NAME', 'unknown')}'")
            else:
                datastream = datastream_for(product, options.content_version)
                if datastream is None:
                    return self._skipped(target, f"no {product} content in {content}")

            profile_id = resolve_profile(options.profile, list_profiles(datastream))
            tailoring_xml = None
            if options.tailoring == BUILTIN_CONTAINER_TAILORING:
                if profile_id is None:
                    return self._skipped(target, f"profile '{options.profile}' not in {product or 'datastream'}")
                profile_id, tailoring_xml = container_tailoring(datastream, profile_id)
            elif options.tailoring != NO_TAILORING:
                tailoring_xml = fetch_file(options.tailoring, self.context).read_text(encoding="utf-8")
                # A custom tailoring may define its own profile; accept a full ID found in it.
                if profile_id is None and f'"{options.profile}"' in tailoring_xml:
                    profile_id = options.profile
            if profile_id is None:
                return self._skipped(target, f"profile '{options.profile}' not in {product or 'datastream'}")
            if tailoring_xml is not None:
                (work_dir / "tailoring.xml").write_text(tailoring_xml, encoding="utf-8")
            provenance["tailoring"] = options.tailoring

            name = self._name()
            cmd = scan_command(
                self.docker,
                self.scanner_image,
                mount_args,
                datastream,
                work_dir,
                profile_id,
                name=name,
                tailoring=tailoring_xml is not None,
                html=OutputFormatEnum.HTML in options.formats,
            )
            log.debug(f"[bright_black]Executing: {' '.join(cmd)}")
            p = self._run_container(cmd, name, capture_output=True)
            oscap_log = (
                (work_dir / "oscap.log").read_text(errors="replace") if (work_dir / "oscap.log").exists() else ""
            )
            results_file = work_dir / "results.xml"
            if p.returncode not in OSCAP_SCAN_RAN_CODES or not results_file.is_file():
                err = BakeryOpenSCAPError(
                    f"oscap evaluation failed for '{target}'",
                    cmd=cmd,
                    stdout=oscap_log or p.stdout,
                    metadata={"oscap_exit_code": p.returncode},
                )
                return TargetOutcome(target, OpenSCAPScanNotRun("ERROR", "oscap evaluation failed"), "ERROR", err)

            report = OpenSCAPScanReport.load(
                results_file,
                profile_id=profile_id,
                content=content,
                product=product,
                os_release=os_release,
                arf_file=work_dir / "arf.xml",
                fix_file=work_dir / "fix.sh",
                skip_rules=options.skip_rules,
            )
            report.provenance.update(provenance)
            self._collect_files(target, report, work_dir, options)

        if not report.valid:
            failed = ", ".join(f"{c.name} ({c.detail})" for c in report.checks if not c.ok)
            err = BakeryOpenSCAPError(f"OpenSCAP results for '{target}' failed validation: {failed}")
            return TargetOutcome(target, report, "ERROR", err)
        if report.breached(options.fail_on):
            err = BakeryOpenSCAPError(
                f"OpenSCAP found failing rules at or above '{options.fail_on.value}' for '{target}'",
                exit_code=OPENSCAP_EXIT_CODE_GATE_BREACH,
            )
            return TargetOutcome(target, report, "BREACH", err)
        return TargetOutcome(target, report, "OK")

    def _skipped(self, target: ImageTarget, reason: str) -> TargetOutcome:
        log.warning(f"[yellow]Skipping OpenSCAP scan of '{target}': {reason}")
        return TargetOutcome(target, OpenSCAPScanNotRun("SKIPPED", reason, skipped=True), "SKIPPED")

    def _output_path(self, target: ImageTarget, suffix: str) -> Path:
        return self.results_dir / target.image_name / f"{target.uid}.{suffix}"

    def _collect_files(
        self, target: ImageTarget, report: OpenSCAPScanReport, work_dir: Path, options: ResolvedOptions
    ) -> None:
        """Copy raw oscap artifacts requested via `formats` out of the scan's work directory."""
        wanted = {
            OutputFormatEnum.HTML: ("report.html", "report.html"),
            OutputFormatEnum.XCCDF: ("results.xml", "results.xml"),
            OutputFormatEnum.ARF: ("arf.xml", "arf.xml"),
            OutputFormatEnum.FIX: ("fix.sh", "fix.sh"),
        }
        for fmt, (src, suffix) in wanted.items():
            if fmt in options.formats and (work_dir / src).is_file():
                dest = self._output_path(target, suffix)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(work_dir / src, dest)
                report.files[fmt.value] = str(dest.relative_to(self.context))

    def _write_outputs(self, outcome: TargetOutcome, options: ResolvedOptions) -> None:
        target, result = outcome.target, outcome.result
        self._output_path(target, "x").parent.mkdir(parents=True, exist_ok=True)
        if isinstance(result, OpenSCAPScanNotRun):
            data = {"image": target_metadata(target), "status": outcome.status, "reason": result.reason}
            if OutputFormatEnum.JSON in options.formats:
                self._output_path(target, "summary.json").write_text(json.dumps(data, indent=2) + "\n")
            return
        json_path = self._output_path(target, "summary.json")
        if OutputFormatEnum.JSON in options.formats:
            result.files["json"] = str(json_path.relative_to(self.context))
        if OutputFormatEnum.MARKDOWN in options.formats:
            md_path = self._output_path(target, "summary.md")
            result.files["markdown"] = str(md_path.relative_to(self.context))
            md_path.write_text(result.to_markdown(target, options.fail_on, outcome.status), encoding="utf-8")
        if OutputFormatEnum.JSON in options.formats:
            json_path.write_text(json.dumps(result.to_dict(target, options.fail_on, outcome.status), indent=2) + "\n")
