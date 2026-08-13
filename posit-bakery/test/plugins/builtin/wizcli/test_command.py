import datetime
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from posit_bakery.image.image_metadata import BuildMetadata
from posit_bakery.plugins.builtin.wizcli.command import WizCLICommand

pytestmark = [
    pytest.mark.unit,
    pytest.mark.wizcli,
]


class TestWizCLICommand:
    def test_from_image_target_basic(self, basic_standard_image_target):
        """Test basic initialization from an image target."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
        )
        assert cmd.image_target == basic_standard_image_target
        assert str(basic_standard_image_target.containerfile) in cmd.command
        assert "--no-color" in cmd.command
        assert "--no-style" in cmd.command
        assert "--json-output-file" in " ".join(cmd.command)

    def test_command_includes_dockerfile(self, basic_standard_image_target):
        """Test that --dockerfile is set to the target's containerfile."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
        )
        idx = cmd.command.index("--dockerfile")
        assert cmd.command[idx + 1] == str(basic_standard_image_target.containerfile)

    def test_command_with_cli_options(self, basic_standard_image_target):
        """Test that CLI options are passed through to the command."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            disabled_scanners="Secret,Malware",
            driver="mount",
            timeout="30m",
            no_publish=True,
        )
        assert "--disabled-scanners" in cmd.command
        assert "Secret,Malware" in cmd.command
        assert "--driver" in cmd.command
        assert "mount" in cmd.command
        assert "--timeout" in cmd.command
        assert "30m" in cmd.command
        assert "--no-publish" in cmd.command

    def test_command_with_tool_options(self, basic_standard_image_target):
        """Test that ToolOptions fields are included in the command."""
        from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            tool_options=WizCLIOptions(
                projects=["proj-1", "proj-2"],
                policies=["pol-1"],
                tags=["team=platform"],
                scanOsManagedLibraries=True,
                scanGoStandardLibrary=False,
            ),
        )
        command_str = " ".join(cmd.command)
        assert "--projects" in command_str
        assert "proj-1,proj-2" in command_str
        assert "--policies" in command_str
        assert "pol-1" in command_str
        assert "--tags" in command_str
        assert "team=platform" in command_str
        assert "--scan-os-managed-libraries=true" in command_str
        assert "--scan-go-standard-library=false" in command_str

    def test_command_cli_policies_projects_override_tool_options(self, basic_standard_image_target):
        """Test that CLI policies/projects win over bakery.yaml tool_options."""
        from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            tool_options=WizCLIOptions(projects=["yaml-proj"], policies=["yaml-pol"]),
            policies="cli-pol-1,cli-pol-2",
            projects="cli-proj",
        )
        command_str = " ".join(cmd.command)
        assert "cli-pol-1,cli-pol-2" in command_str
        assert "yaml-pol" not in command_str
        assert "cli-proj" in command_str
        assert "yaml-proj" not in command_str

    def test_command_policies_projects_fall_back_to_tool_options(self, basic_standard_image_target):
        """Test that policies/projects come from tool_options when no CLI value is given."""
        from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            tool_options=WizCLIOptions(projects=["yaml-proj"], policies=["yaml-pol"]),
        )
        command_str = " ".join(cmd.command)
        assert "yaml-pol" in command_str
        assert "yaml-proj" in command_str

    def test_command_with_auth_options(self, basic_standard_image_target):
        """Test that auth CLI options are passed through."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            client_id="my-id",
            client_secret="my-secret",
        )
        assert "--client-id" in cmd.command
        assert "my-id" in cmd.command
        assert "--client-secret" in cmd.command
        assert "my-secret" in cmd.command

    def test_command_with_device_code_flags(self, basic_standard_image_target):
        """Test that boolean auth flags are included when set."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            use_device_code=True,
            no_browser=True,
        )
        assert "--use-device-code" in cmd.command
        assert "--no-browser" in cmd.command

    def test_scan_name_format(self, basic_standard_image_target):
        """Test that scan_name follows the Version-OS-Variant-platform format.

        With no explicit platform the scan targets the host platform, mirroring
        ``ImageTarget.ref()``'s own default.
        """
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        with patch("posit_bakery.plugins.builtin.wizcli.command.SETTINGS") as mock_settings:
            mock_settings.architecture = "amd64"
            cmd = WizCLICommand.from_image_target(
                image_target=basic_standard_image_target,
                results_dir=results_dir,
            )
            assert cmd.platform == "linux/amd64"
            # Literal rather than re-derived from tag_template_values: computing the
            # expectation with the same expression as scan_name would agree with the
            # implementation even if both were wrong.
            assert cmd.scan_name == "test-image:1.0.0-ubuntu-22.04-std-amd64"
            assert "--name" in cmd.command
            assert cmd.scan_name in cmd.command

    def test_scan_name_in_command(self, basic_standard_image_target):
        """Test that --name flag uses scan_name, labelled with the requested platform."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        with patch("posit_bakery.plugins.builtin.wizcli.command.SETTINGS") as mock_settings:
            mock_settings.architecture = "amd64"
            cmd = WizCLICommand.from_image_target(
                image_target=basic_standard_image_target,
                results_dir=results_dir,
                platform="linux/arm64",
            )
            idx = cmd.command.index("--name")
            assert cmd.command[idx + 1].endswith("-arm64")

    @pytest.mark.parametrize(
        "requested_arch,host_arch",
        [
            ("arm64", "amd64"),
            ("amd64", "arm64"),
        ],
    )
    def test_scan_targets_requested_platform_not_host(self, basic_standard_image_target, requested_arch, host_arch):
        """Regression: the requested platform, not the host arch, drives the scan.

        ``--image-platform`` must select which build metadata digest is scanned and
        which arch labels the scan in Wiz. A host-arch fallback finds no matching
        metadata and silently degrades to a mutable registry tag, so the scanner
        reports on the wrong artifact under the wrong labels.
        """
        build_metadata = []
        for arch in ("amd64", "arm64"):
            metadata = MagicMock(spec=BuildMetadata)
            metadata.platform = f"linux/{arch}"
            metadata.image_ref = f"docker.io/posit/test-image:1.0.0@sha256:{arch}digest"
            metadata.digest_ref = f"docker.io/posit/test-image@sha256:{arch}digest"
            metadata.created_at = datetime.datetime.now()
            build_metadata.append(metadata)
        basic_standard_image_target.build_metadata = build_metadata

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        with patch("posit_bakery.plugins.builtin.wizcli.command.SETTINGS") as mock_settings:
            mock_settings.architecture = host_arch
            cmd = WizCLICommand.from_image_target(
                image_target=basic_standard_image_target,
                results_dir=results_dir,
                platform=f"linux/{requested_arch}",
            )
            command = cmd.command

        # The exact digest built for the requested platform, never the host's and never a tag.
        assert f"docker.io/posit/test-image@sha256:{requested_arch}digest" in command
        assert f"docker.io/posit/test-image@sha256:{host_arch}digest" not in command
        assert not [arg for arg in command if arg.startswith("docker.io/posit/test-image:")]

        assert command[command.index("--name") + 1].endswith(f"-{requested_arch}")

        tags = [command[i + 1] for i, arg in enumerate(command) if arg == "--tags"]
        assert f"platform={requested_arch}" in tags
        assert f"platform={host_arch}" not in tags

    def test_scan_tags_present(self, basic_standard_image_target):
        """Test the exact set of auto-generated scan tags emitted in the command.

        Asserting values rather than keys: a wrong platform or OS value is the
        failure mode that actually corrupts grouping in the Wiz UI, and a
        key-presence check cannot see it.
        """
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        with patch("posit_bakery.plugins.builtin.wizcli.command.SETTINGS") as mock_settings:
            mock_settings.architecture = "amd64"
            cmd = WizCLICommand.from_image_target(
                image_target=basic_standard_image_target,
                results_dir=results_dir,
            )
            tags_in_command = [cmd.command[i + 1] for i, arg in enumerate(cmd.command) if arg == "--tags"]
        assert tags_in_command == [
            "product=test-image",
            "version=1.0.0",
            "channel=release",
            "platform=amd64",
            "base-os=ubuntu-22.04",
            "variant=std",
        ]

    def test_scan_tags_omit_absent_os_and_variant(self, basic_standard_image_target):
        """Test that the optional base-os/variant tags are skipped, not emitted empty.

        Wiz rejects tag keys shorter than three characters and an empty value would
        create a junk grouping bucket, so these two must drop out entirely.
        """
        basic_standard_image_target.image_os = None
        basic_standard_image_target.image_variant = None

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        with patch("posit_bakery.plugins.builtin.wizcli.command.SETTINGS") as mock_settings:
            mock_settings.architecture = "amd64"
            cmd = WizCLICommand.from_image_target(
                image_target=basic_standard_image_target,
                results_dir=results_dir,
            )
            tags_in_command = [cmd.command[i + 1] for i, arg in enumerate(cmd.command) if arg == "--tags"]
        assert tags_in_command == [
            "product=test-image",
            "version=1.0.0",
            "channel=release",
            "platform=amd64",
        ]

    def test_scan_tags_user_tags_appended(self, basic_standard_image_target):
        """Test that user-supplied tags are emitted after auto-generated ones."""
        from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions
        from unittest.mock import patch

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        with patch("posit_bakery.plugins.builtin.wizcli.command.SETTINGS") as mock_settings:
            mock_settings.architecture = "amd64"
            cmd = WizCLICommand.from_image_target(
                image_target=basic_standard_image_target,
                results_dir=results_dir,
                tool_options=WizCLIOptions(tags=["team=platform"]),
            )
            tags_in_command = [cmd.command[i + 1] for i, arg in enumerate(cmd.command) if arg == "--tags"]
            assert "team=platform" in tags_in_command
            # Auto tags appear before user tags
            auto_idx = next(i for i, t in enumerate(tags_in_command) if t.startswith("product="))
            user_idx = tags_in_command.index("team=platform")
            assert auto_idx < user_idx

    def test_scan_tags_include_base_digest_from_build_metadata(self, basic_standard_image_target):
        """Test that a base-digest tag is added when build metadata is available.

        Neither `version` nor a coarse scan-context-id changes between rebuilds of the same
        release, so this is the only tag that can answer which base image produced a given scan.
        """
        metadata = MagicMock(spec=BuildMetadata)
        metadata.platform = "linux/amd64"
        metadata.created_at = datetime.datetime.now()
        metadata.base_image_digest.return_value = (
            "sha256:104ae83764a5119017b8e8d6218fa0832b09df65aae7d5a6de29a85d813da2f"
        )
        basic_standard_image_target.build_metadata = [metadata]

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        with patch("posit_bakery.plugins.builtin.wizcli.command.SETTINGS") as mock_settings:
            mock_settings.architecture = "amd64"
            cmd = WizCLICommand.from_image_target(
                image_target=basic_standard_image_target,
                results_dir=results_dir,
            )
            # `command` is a computed_field property that recomputes from scratch on every
            # access rather than caching, so read it once rather than inline in a comprehension.
            command = cmd.command
            tags_in_command = [command[i + 1] for i, arg in enumerate(command) if arg == "--tags"]

        assert "base-digest=sha256:104ae83764a5119017b8e8d6218fa0832b09df65aae7d5a6de29a85d813da2f" in tags_in_command
        metadata.base_image_digest.assert_called_once_with(basic_standard_image_target.image_os.buildOS.name)

    def test_scan_tags_omit_base_digest_without_build_metadata(self, basic_standard_image_target):
        """Test that base-digest is absent, not empty, without build metadata."""
        assert basic_standard_image_target.build_metadata == []

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        with patch("posit_bakery.plugins.builtin.wizcli.command.SETTINGS") as mock_settings:
            mock_settings.architecture = "amd64"
            cmd = WizCLICommand.from_image_target(
                image_target=basic_standard_image_target,
                results_dir=results_dir,
            )
            tags_in_command = [cmd.command[i + 1] for i, arg in enumerate(cmd.command) if arg == "--tags"]

        assert not any(tag.startswith("base-digest=") for tag in tags_in_command)

    @pytest.mark.parametrize(
        "version,expected",
        [
            ("2026.07.0", "test-image-2026-07-ubuntu-22-04-std-amd64"),
            ("2026.07.12", "test-image-2026-07-ubuntu-22-04-std-amd64"),
            ("2026.08.1-2", "test-image-2026-08-ubuntu-22-04-std-amd64"),
            ("2026.07.0+build.5", "test-image-2026-07-ubuntu-22-04-std-amd64"),
            ("R4.5-python3.14", "test-image-r4-5-python3-14-ubuntu-22-04-std-amd64"),
        ],
        ids=["patch", "two-digit-patch", "positron-build-number", "build-metadata", "matrix"],
    )
    def test_release_context_id_stays_stable_per_artifact(self, basic_standard_image_target, version, expected):
        """Test that patch bumps, build numbers, and build metadata share an artifact context.

        The context must update in place across a release without allowing different
        OSes, variants, or platforms to select each other as a baseline.
        """
        basic_standard_image_target.image_version.name = version

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
        )
        assert cmd.default_scan_context_id == expected
        assert cmd.command[cmd.command.index("--scan-context-id") + 1] == expected

    def test_scan_context_id_dev_uses_channel(self, basic_standard_image_target):
        """Test that dev builds use a per-channel, per-artifact context ID."""
        from unittest.mock import PropertyMock, patch
        from posit_bakery.config.image.posit_product.const import ReleaseChannelEnum

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        with patch.object(
            type(basic_standard_image_target),
            "release_channel",
            new_callable=PropertyMock,
            return_value=ReleaseChannelEnum.DAILY,
        ):
            cmd = WizCLICommand.from_image_target(
                image_target=basic_standard_image_target,
                results_dir=results_dir,
            )
            idx = cmd.command.index("--scan-context-id")
            assert cmd.command[idx + 1] == f"{basic_standard_image_target.image_name}-daily-ubuntu-22-04-std-amd64"

    def test_scan_context_id_omits_absent_dimensions(self, basic_standard_image_target):
        """Test that targets without OS or variant axes have no empty ID components."""
        basic_standard_image_target.image_os = None
        basic_standard_image_target.image_variant = None

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
        )
        assert cmd.default_scan_context_id == "test-image-1-0-amd64"

    def test_scan_context_id_explicit_override(self, basic_standard_image_target):
        """Test that an explicit scan_context_id overrides the uid default."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            scan_context_id="my-custom-context",
        )
        idx = cmd.command.index("--scan-context-id")
        assert cmd.command[idx + 1] == "my-custom-context"

    def test_validate_no_wizcli_bin(self, basic_standard_image_target):
        """Test that validation fails if wizcli binary cannot be found."""
        with patch("posit_bakery.plugins.builtin.wizcli.command.find_wizcli_bin") as mock:
            mock.return_value = None
            with pytest.raises(ValidationError, match="wizcli binary path must be specified"):
                results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
                WizCLICommand.from_image_target(
                    image_target=basic_standard_image_target,
                    results_dir=results_dir,
                )
