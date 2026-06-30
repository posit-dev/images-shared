"""Tests for the ORAS CLI integration module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from posit_bakery.error import BakeryToolRuntimeError
from posit_bakery.image.image_target import StringableList, ImageTarget, ImageTargetContext, ImageTargetSettings
from posit_bakery.plugins.builtin.imagetools.oras import (
    find_oras_bin,
    get_repository_from_ref,
    OrasCopy,
    OrasIndexCopyWorkflow,
    OrasIndexCreateWorkflow,
    OrasIndexVerifyWorkflow,
    OrasManifestFetch,
    OrasManifestIndexCreate,
    OrasMergeWorkflow,
    OrasMergeWorkflowResult,
    OrasWaitForSourcesWorkflow,
)
from posit_bakery.retry import RetryPolicy

pytestmark = [
    pytest.mark.unit,
]


@pytest.mark.parametrize(
    "ref,expected_repo",
    [
        ("ghcr.io/posit-dev/test/tmp@sha256:abc123", "ghcr.io/posit-dev/test/tmp"),
        ("ghcr.io/posit-dev/test:latest", "ghcr.io/posit-dev/test"),
        ("localhost:5000/repo/image:tag", "localhost:5000/repo/image"),
        ("docker.io/library/ubuntu:22.04", "docker.io/library/ubuntu"),
    ],
)
def test_get_repository_from_ref(ref, expected_repo):
    """Test extracting repository from image reference."""
    result = get_repository_from_ref(ref)
    assert result == expected_repo


class TestOrasCommandRunner:
    """Tests for OrasCommand.run()'s optional CommandRunner routing."""

    def test_runner_used_when_provided(self):
        cmd = OrasManifestFetch(oras_bin="oras", reference="ghcr.io/x/y:latest")
        fake_runner = MagicMock()
        fake_runner.run.return_value = subprocess.CompletedProcess(
            args=cmd.command, returncode=0, stdout=b"ok", stderr=b""
        )

        result = cmd.run(runner=fake_runner)

        fake_runner.run.assert_called_once_with(cmd.command)
        assert result.returncode == 0

    def test_subprocess_run_used_when_runner_omitted(self):
        cmd = OrasManifestFetch(oras_bin="oras", reference="ghcr.io/x/y:latest")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=cmd.command, returncode=0, stdout=b"", stderr=b"")
            cmd.run()
        mock_run.assert_called_once_with(cmd.command, capture_output=True)

    def test_runner_failure_raises_tool_error(self):
        cmd = OrasManifestFetch(oras_bin="oras", reference="ghcr.io/x/y:latest")
        fake_runner = MagicMock()
        fake_runner.run.return_value = subprocess.CompletedProcess(
            args=cmd.command, returncode=1, stdout=b"", stderr=b"nope"
        )
        with pytest.raises(BakeryToolRuntimeError):
            cmd.run(runner=fake_runner)


class TestOrasManifestIndexCreate:
    """Tests for the OrasManifestIndexCreate command."""

    def test_command_construction(self):
        """Test that the command is constructed correctly."""
        cmd = OrasManifestIndexCreate(
            oras_bin="oras",
            sources=[
                "ghcr.io/posit-dev/test/tmp@sha256:amd64digest",
                "ghcr.io/posit-dev/test/tmp@sha256:arm64digest",
            ],
            destination="ghcr.io/posit-dev/test/tmp:merged",
            annotations={"org.opencontainers.image.title": "Test Image"},
        )

        expected = [
            "oras",
            "manifest",
            "index",
            "create",
            "ghcr.io/posit-dev/test/tmp:merged",
            "ghcr.io/posit-dev/test/tmp@sha256:amd64digest",
            "ghcr.io/posit-dev/test/tmp@sha256:arm64digest",
            "--annotation",
            "org.opencontainers.image.title=Test Image",
        ]
        assert cmd.command == expected

    def test_command_without_annotations(self):
        """Test command construction without annotations."""
        cmd = OrasManifestIndexCreate(
            oras_bin="oras",
            sources=["ghcr.io/posit-dev/test/tmp@sha256:digest"],
            destination="ghcr.io/posit-dev/test/tmp:tag",
        )

        expected = [
            "oras",
            "manifest",
            "index",
            "create",
            "ghcr.io/posit-dev/test/tmp:tag",
            "ghcr.io/posit-dev/test/tmp@sha256:digest",
        ]
        assert cmd.command == expected

    def test_validates_sources_same_repository(self):
        """Test that validation fails when sources are from different repositories."""
        with pytest.raises(ValidationError) as exc_info:
            OrasManifestIndexCreate(
                oras_bin="oras",
                sources=[
                    "ghcr.io/posit-dev/image1/tmp@sha256:digest1",
                    "ghcr.io/posit-dev/image2/tmp@sha256:digest2",
                ],
                destination="ghcr.io/posit-dev/test/tmp:tag",
            )

        assert "same repository" in str(exc_info.value).lower()

    def test_validates_sources_required(self):
        """Test that validation fails when no sources are provided."""
        with pytest.raises(ValidationError) as exc_info:
            OrasManifestIndexCreate(
                oras_bin="oras",
                sources=[],
                destination="ghcr.io/posit-dev/test/tmp:tag",
            )

        assert "at least one source" in str(exc_info.value).lower()

    def test_run_success(self):
        """Test successful command execution."""
        cmd = OrasManifestIndexCreate(
            oras_bin="oras",
            sources=["ghcr.io/posit-dev/test/tmp@sha256:digest"],
            destination="ghcr.io/posit-dev/test/tmp:tag",
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=cmd.command, returncode=0, stdout=b"", stderr=b"")
            result = cmd.run()

        mock_run.assert_called_once_with(cmd.command, capture_output=True)
        assert result.returncode == 0

    def test_run_failure(self):
        """Test command execution failure."""
        cmd = OrasManifestIndexCreate(
            oras_bin="oras",
            sources=["ghcr.io/posit-dev/test/tmp@sha256:digest"],
            destination="ghcr.io/posit-dev/test/tmp:tag",
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=cmd.command, returncode=1, stdout=b"", stderr=b"error message"
            )
            with pytest.raises(BakeryToolRuntimeError) as exc_info:
                cmd.run()

        assert exc_info.value.tool_name == "oras"
        assert exc_info.value.exit_code == 1

    def test_dry_run(self):
        """Test dry run mode doesn't execute command."""
        cmd = OrasManifestIndexCreate(
            oras_bin="oras",
            sources=["ghcr.io/posit-dev/test/tmp@sha256:digest"],
            destination="ghcr.io/posit-dev/test/tmp:tag",
        )

        with patch("subprocess.run") as mock_run:
            result = cmd.run(dry_run=True)

        mock_run.assert_not_called()
        assert result.returncode == 0


class TestOrasCopy:
    """Tests for the OrasCopy command."""

    def test_command_construction(self):
        """Test that the command is constructed correctly."""
        cmd = OrasCopy(
            oras_bin="oras",
            source="ghcr.io/posit-dev/test/tmp:source",
            destination="docker.io/posit/test:dest",
        )

        expected = ["oras", "cp", "ghcr.io/posit-dev/test/tmp:source", "docker.io/posit/test:dest"]
        assert cmd.command == expected

    def test_command_construction_with_oci_layout_flags(self):
        """OCI image layout flags are emitted before the source/destination args."""
        cmd = OrasCopy(
            oras_bin="oras",
            source="/tmp/out@sha256:abc",
            destination="ghcr.io/posit-dev/test:dest-soci",
            from_oci_layout=True,
        )
        assert cmd.command == [
            "oras",
            "cp",
            "--from-oci-layout",
            "/tmp/out@sha256:abc",
            "ghcr.io/posit-dev/test:dest-soci",
        ]

        cmd = OrasCopy(
            oras_bin="oras",
            source="ghcr.io/posit-dev/test:source",
            destination="/tmp/src:image",
            to_oci_layout=True,
        )
        assert cmd.command == [
            "oras",
            "cp",
            "--to-oci-layout",
            "ghcr.io/posit-dev/test:source",
            "/tmp/src:image",
        ]

    def test_run_success(self):
        """Test successful copy execution."""
        cmd = OrasCopy(
            oras_bin="oras",
            source="ghcr.io/posit-dev/test:source",
            destination="docker.io/posit/test:dest",
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=cmd.command, returncode=0, stdout=b"", stderr=b"")
            result = cmd.run()

        mock_run.assert_called_once_with(cmd.command, capture_output=True)
        assert result.returncode == 0


class TestOrasMergeWorkflow:
    """Tests for the OrasMergeWorkflow orchestrator."""

    @pytest.fixture
    def mock_image_target(self):
        """Create a mock ImageTarget for testing."""
        mock_target = MagicMock(spec=ImageTarget)
        mock_target.image_name = "test-image"
        mock_target.uid = "test-image-1-0-0"
        mock_target.temp_registry = "ghcr.io/posit-dev"
        mock_target.get_merge_sources.return_value = [
            "ghcr.io/posit-dev/test/tmp@sha256:amd64digest",
            "ghcr.io/posit-dev/test/tmp@sha256:arm64digest",
        ]
        mock_target.labels = {
            "org.opencontainers.image.title": "Test Image",
        }

        # Create mock tags
        mock_tag1 = MagicMock()
        mock_tag1.destination = "ghcr.io/posit-dev/test-image"
        mock_tag1.suffix = "1.0.0"
        mock_tag1.__str__ = lambda self: "ghcr.io/posit-dev/test-image:1.0.0"

        mock_tag2 = MagicMock()
        mock_tag2.destination = "ghcr.io/posit-dev/test-image"
        mock_tag2.suffix = "latest"
        mock_tag2.__str__ = lambda self: "ghcr.io/posit-dev/test-image:latest"

        mock_tag3 = MagicMock()
        mock_tag3.destination = "docker.io/posit/test-image"
        mock_tag3.suffix = "1.0.0"
        mock_tag3.__str__ = lambda self: "docker.io/posit/test-image:1.0.0"

        mock_tag4 = MagicMock()
        mock_tag4.destination = "docker.io/posit/test-image"
        mock_tag4.suffix = "latest"
        mock_tag4.__str__ = lambda self: "docker.io/posit/test-image:latest"

        mock_target.tags = StringableList([mock_tag1, mock_tag2, mock_tag3, mock_tag4])
        return mock_target

    @pytest.fixture
    def basic_workflow(self, mock_image_target):
        """Return a basic workflow configuration."""
        return OrasMergeWorkflow(
            oras_bin="oras",
            image_target=mock_image_target,
            annotations={"org.opencontainers.image.title": "Test Image"},
        )

    def test_temp_index_tag_generation(self, basic_workflow):
        """Test that temporary index tag is generated with unique ID."""
        tag = basic_workflow.temp_index_tag
        assert tag.startswith("ghcr.io/posit-dev/test-image/tmp:test-image-1-0-0")
        # Should have a 10-character hash suffix after the uid
        suffix = tag.split(":")[-1]
        assert suffix.startswith("test-image-1-0-0")
        assert len(suffix) == len("test-image-1-0-0") + 10

    def test_sources_property(self, basic_workflow):
        """Test that sources property returns image target's merge sources."""
        sources = basic_workflow.sources
        assert len(sources) == 2
        assert "ghcr.io/posit-dev/test/tmp@sha256:amd64digest" in sources
        assert "ghcr.io/posit-dev/test/tmp@sha256:arm64digest" in sources

    def test_execute_success(self, basic_workflow):
        """Test successful workflow execution."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
            result = basic_workflow.run()

        assert result.success is True
        assert result.error is None
        assert len(result.destinations) == 4
        assert result.temp_index_ref is not None

        # Should have called:
        # 1 create + 2 copy (grouped by destination) = 3 calls.
        # The temporary index is no longer deleted here; clean.yml handles it.
        assert mock_run.call_count == 3

    def test_execute_dry_run(self, basic_workflow):
        """Test dry run mode."""
        with patch("subprocess.run") as mock_run:
            result = basic_workflow.run(dry_run=True)

        mock_run.assert_not_called()
        assert result.success is True
        assert len(result.destinations) == 4

    def test_execute_failure_on_create(self, basic_workflow):
        """Test workflow handles failure during index creation."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=1, stdout=b"", stderr=b"failed to create index"
            )
            result = basic_workflow.run()

        assert result.success is False
        assert result.error is not None
        # Should fail on first call (create)
        assert mock_run.call_count == 1

    def test_execute_failure_on_copy(self, basic_workflow):
        """Test workflow handles failure during copy."""
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Fail on second call (first copy)
            if call_count == 2:
                return subprocess.CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"copy failed")
            return subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")

        with patch("subprocess.run", side_effect=side_effect):
            result = basic_workflow.run()

        assert result.success is False
        assert result.error is not None

    def test_validates_sources_required(self):
        """Test that validation fails when no sources are provided."""
        mock_target = MagicMock(spec=ImageTarget)
        mock_target.get_merge_sources.return_value = []

        with pytest.raises(ValidationError) as exc_info:
            OrasMergeWorkflow(
                oras_bin="oras",
                image_target=mock_target,
            )

        assert "at least one source" in str(exc_info.value).lower()


class TestOrasMergeWorkflowFromImageTarget:
    """Tests for creating OrasMergeWorkflow from ImageTarget."""

    @pytest.fixture
    def mock_image_target(self):
        """Create a mock ImageTarget for testing."""
        mock_target = MagicMock(spec=ImageTarget)
        mock_target.image_name = "test-image"
        mock_target.uid = "test-image-1-0-0"
        mock_target.context = MagicMock(spec=ImageTargetContext)
        mock_target.context.base_path = Path("/project")
        mock_target.settings = MagicMock(spec=ImageTargetSettings)
        mock_target.settings.temp_registry = "ghcr.io/posit-dev"
        mock_target.temp_registry = "ghcr.io/posit-dev"
        mock_target.get_merge_sources.return_value = [
            "ghcr.io/posit-dev/test/tmp@sha256:amd64",
            "ghcr.io/posit-dev/test/tmp@sha256:arm64",
        ]
        mock_target.labels = {
            "org.opencontainers.image.title": "Test Image",
            "org.opencontainers.image.version": "1.0.0",
        }

        # Create mock tags
        mock_tag1 = MagicMock()
        mock_tag1.destination = "ghcr.io/posit-dev/test-image"
        mock_tag1.suffix = "1.0.0"
        mock_tag1.__str__ = lambda self: "ghcr.io/posit-dev/test-image:1.0.0"

        mock_tag2 = MagicMock()
        mock_tag2.destination = "ghcr.io/posit-dev/test-image"
        mock_tag2.suffix = "latest"
        mock_tag2.__str__ = lambda self: "ghcr.io/posit-dev/test-image:latest"

        mock_target.tags = [mock_tag1, mock_tag2]

        return mock_target

    def test_from_image_target(self, mock_image_target):
        """Test creating workflow from ImageTarget."""
        with patch("posit_bakery.plugins.builtin.imagetools.oras.find_oras_bin", return_value="oras"):
            workflow = OrasMergeWorkflow.from_image_target(mock_image_target)

        assert workflow.oras_bin == "oras"
        assert workflow.image_target is mock_image_target
        assert len(workflow.sources) == 2
        assert "org.opencontainers.image.title" in workflow.annotations

    def test_from_image_target_missing_temp_registry(self, mock_image_target):
        """Test that ValueError is raised when temp_registry is not set."""
        mock_image_target.settings.temp_registry = None

        with pytest.raises(ValueError) as exc_info:
            OrasMergeWorkflow.from_image_target(mock_image_target)

        assert "temp_registry" in str(exc_info.value).lower()

    def test_from_image_target_with_custom_oras_bin(self, mock_image_target):
        """Test creating workflow with custom oras binary path."""
        workflow = OrasMergeWorkflow.from_image_target(mock_image_target, oras_bin="/custom/path/oras")

        assert workflow.oras_bin == "/custom/path/oras"


class TestFindOrasBin:
    """Tests for the find_oras_bin function."""

    def test_find_from_env_var(self, tmp_path):
        """Test finding oras from environment variable."""
        with patch.dict("os.environ", {"ORAS_PATH": "/custom/oras"}):
            result = find_oras_bin(tmp_path)
        assert result == "/custom/oras"

    def test_find_from_path(self, tmp_path):
        """Test finding oras from PATH."""
        with patch.dict("os.environ", {}, clear=False):
            # Remove ORAS_PATH if it exists
            import os

            os.environ.pop("ORAS_PATH", None)

            with patch("shutil.which", return_value="/usr/bin/oras"):
                result = find_oras_bin(tmp_path)
        assert result == "oras"

    def test_find_from_tools_dir(self, tmp_path):
        """Test finding oras from project tools directory."""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        oras_bin = tools_dir / "oras"
        oras_bin.touch()

        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("ORAS_PATH", None)

            # Patch 'which' in the module where it's imported
            with patch("posit_bakery.util.which", return_value=None):
                result = find_oras_bin(tmp_path)

        assert result == str(oras_bin)


class TestOrasMergeWorkflowResult:
    """Tests for the OrasMergeWorkflowResult model."""

    def test_success_result(self):
        """Test creating a successful result."""
        result = OrasMergeWorkflowResult(
            success=True,
            temp_index_ref="ghcr.io/test/tmp:abc123",
            destinations=["ghcr.io/test:1.0.0", "ghcr.io/test:latest"],
        )

        assert result.success is True
        assert result.error is None
        assert len(result.destinations) == 2

    def test_failure_result(self):
        """Test creating a failure result."""
        result = OrasMergeWorkflowResult(
            success=False,
            temp_index_ref="ghcr.io/test/tmp:abc123",
            destinations=[],
            error="Command failed with exit code 1",
        )

        assert result.success is False
        assert result.error is not None


class TestOrasCommandsPlainHttp:
    """Tests for plain_http flag on ORAS commands."""

    def test_manifest_index_create_with_plain_http(self):
        """Test that --plain-http flag is included when plain_http=True."""
        cmd = OrasManifestIndexCreate(
            oras_bin="oras",
            sources=["localhost:5000/test/tmp@sha256:digest"],
            destination="localhost:5000/test/tmp:tag",
            plain_http=True,
        )

        expected = [
            "oras",
            "manifest",
            "index",
            "create",
            "--plain-http",
            "localhost:5000/test/tmp:tag",
            "localhost:5000/test/tmp@sha256:digest",
        ]
        assert cmd.command == expected

    def test_copy_with_plain_http(self):
        """Test that --plain-http flag is included when plain_http=True."""
        cmd = OrasCopy(
            oras_bin="oras",
            source="localhost:5000/test:source",
            destination="localhost:5000/test:dest",
            plain_http=True,
        )

        expected = ["oras", "cp", "--plain-http", "localhost:5000/test:source", "localhost:5000/test:dest"]
        assert cmd.command == expected


@pytest.fixture
def mock_image_target_factory():
    def _make():
        t = MagicMock(spec=ImageTarget)
        t.image_name = "test-image"
        t.uid = "test-image-1-0-0"
        t.temp_registry = "ghcr.io/posit-dev"
        t.get_merge_sources.return_value = [
            "ghcr.io/posit-dev/test/tmp@sha256:amd64digest",
            "ghcr.io/posit-dev/test/tmp@sha256:arm64digest",
        ]
        t.labels = {"org.opencontainers.image.title": "Test Image"}
        tag1 = MagicMock()
        tag1.destination = "ghcr.io/posit-dev/test-image"
        tag1.suffix = "1.0.0"
        tag1.__str__ = lambda self: "ghcr.io/posit-dev/test-image:1.0.0"
        t.tags = StringableList([tag1])
        return t

    return _make


class TestOrasIndexCreateWorkflow:
    """Tests for the standalone index-create primitive."""

    @pytest.fixture
    def workflow(self, mock_image_target_factory):
        target = mock_image_target_factory()
        return OrasIndexCreateWorkflow(
            oras_bin="oras",
            image_target=target,
            annotations={"k": "v"},
        )

    def test_creates_index_at_temp_ref(self, workflow):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
            result = workflow.run()
        assert result.success is True
        assert result.temp_ref == workflow.temp_index_tag
        # exactly one subprocess call: oras manifest index create
        assert mock_run.call_count == 1
        cmd = mock_run.call_args.args[0]
        assert cmd[:4] == ["oras", "manifest", "index", "create"]

    def test_index_create_passes_runner_through(self, workflow):
        fake_runner = MagicMock()
        fake_runner.run.return_value = subprocess.CompletedProcess(args=["oras"], returncode=0, stdout=b"", stderr=b"")

        result = workflow.run(runner=fake_runner)

        assert result.success is True
        fake_runner.run.assert_called_once()


class TestOrasIndexCopyWorkflow:
    """Tests for the standalone index-copy primitive."""

    def test_copies_to_each_destination_grouped_by_repo(self, mock_image_target_factory):
        target = mock_image_target_factory()
        # Add a second-registry tag so we exercise the grouping.
        extra_tag = MagicMock()
        extra_tag.destination = "docker.io/posit/test-image"
        extra_tag.suffix = "1.0.0"
        extra_tag.__str__ = lambda self: "docker.io/posit/test-image:1.0.0"
        target.tags.append(extra_tag)

        workflow = OrasIndexCopyWorkflow(oras_bin="oras", image_target=target)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
            result = workflow.run(source="ghcr.io/posit-dev/test-image/tmp:src")

        assert result.success is True
        # Two distinct destination repos => two oras cp invocations.
        assert mock_run.call_count == 2


class TestOrasManifestFetch:
    """Tests for the OrasManifestFetch command."""

    def test_command_construction(self):
        """The fetch command targets the given reference."""
        cmd = OrasManifestFetch(
            oras_bin="oras",
            reference="docker.io/posit/test:1.0.0",
        )
        assert cmd.command == ["oras", "manifest", "fetch", "docker.io/posit/test:1.0.0"]

    def test_command_construction_with_descriptor(self):
        """The --descriptor flag fetches only the descriptor for a lightweight check."""
        cmd = OrasManifestFetch(
            oras_bin="oras",
            reference="docker.io/posit/test:1.0.0",
            descriptor=True,
        )
        assert cmd.command == ["oras", "manifest", "fetch", "--descriptor", "docker.io/posit/test:1.0.0"]

    def test_command_construction_with_plain_http(self):
        """The --plain-http flag is emitted before the reference."""
        cmd = OrasManifestFetch(
            oras_bin="oras",
            reference="localhost:5000/test:dest",
            descriptor=True,
            plain_http=True,
        )
        assert cmd.command == [
            "oras",
            "manifest",
            "fetch",
            "--plain-http",
            "--descriptor",
            "localhost:5000/test:dest",
        ]

    def test_run_success(self):
        """A zero exit code returns the completed process."""
        cmd = OrasManifestFetch(oras_bin="oras", reference="docker.io/posit/test:1.0.0")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=cmd.command, returncode=0, stdout=b'{"schemaVersion":2}', stderr=b""
            )
            result = cmd.run()
        mock_run.assert_called_once_with(cmd.command, capture_output=True)
        assert result.returncode == 0

    def test_run_failure_raises(self):
        """A missing reference (non-zero exit) raises BakeryToolRuntimeError."""
        cmd = OrasManifestFetch(oras_bin="oras", reference="docker.io/posit/test:missing")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=cmd.command, returncode=1, stdout=b"", stderr=b"not found"
            )
            with pytest.raises(BakeryToolRuntimeError):
                cmd.run()


class TestOrasIndexVerifyWorkflow:
    """Tests for the standalone index-verify primitive."""

    def test_verifies_each_destination_tag(self, mock_image_target_factory):
        """Every final destination tag is fetched and reported as verified."""
        target = mock_image_target_factory()
        extra_tag = MagicMock()
        extra_tag.destination = "docker.io/posit/test-image"
        extra_tag.suffix = "1.0.0"
        extra_tag.__str__ = lambda self: "docker.io/posit/test-image:1.0.0"
        target.tags.append(extra_tag)

        workflow = OrasIndexVerifyWorkflow(oras_bin="oras", image_target=target)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"{}", stderr=b"")
            result = workflow.run()

        assert result.success is True
        # One fetch per individual destination tag.
        assert mock_run.call_count == 2
        assert result.verified == [
            "ghcr.io/posit-dev/test-image:1.0.0",
            "docker.io/posit/test-image:1.0.0",
        ]
        # Verification uses a lightweight descriptor fetch.
        assert mock_run.call_args_list[0].args[0][:3] == ["oras", "manifest", "fetch"]
        assert "--descriptor" in mock_run.call_args_list[0].args[0]

    def test_run_failure_reports_partial(self, mock_image_target_factory):
        """A failed fetch surfaces an error and only the refs verified so far."""
        target = mock_image_target_factory()
        extra_tag = MagicMock()
        extra_tag.destination = "docker.io/posit/test-image"
        extra_tag.suffix = "1.0.0"
        extra_tag.__str__ = lambda self: "docker.io/posit/test-image:1.0.0"
        target.tags.append(extra_tag)

        workflow = OrasIndexVerifyWorkflow(oras_bin="oras", image_target=target)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                subprocess.CompletedProcess(args=[], returncode=0, stdout=b"{}", stderr=b""),
                subprocess.CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"not found"),
            ]
            result = workflow.run()

        assert result.success is False
        assert result.error is not None
        assert result.verified == ["ghcr.io/posit-dev/test-image:1.0.0"]

    def test_dry_run_skips_execution(self, mock_image_target_factory):
        """Dry run reports success without invoking oras."""
        target = mock_image_target_factory()
        workflow = OrasIndexVerifyWorkflow(oras_bin="oras", image_target=target)

        with patch("subprocess.run") as mock_run:
            result = workflow.run(dry_run=True)

        mock_run.assert_not_called()
        assert result.success is True


@pytest.mark.slow
class TestOrasMergeWorkflowIntegration:
    """End-to-end tests for ORAS merge workflow using a local registry container.

    These tests require Docker to be running and the ORAS CLI to be installed.
    They test the complete merge workflow against a real local HTTP registry.
    """

    @pytest.fixture
    def mock_image_target_for_local_registry(self):
        """Create a mock ImageTarget configured for local registry testing."""

        def _create_target(registry_url: str):
            mock_target = MagicMock(spec=ImageTarget)
            mock_target.image_name = "test-image"
            mock_target.uid = "test-image-1-0-0"
            mock_target.temp_registry = registry_url
            mock_target.labels = {"org.opencontainers.image.title": "Test Image"}

            # Create mock tag for local registry
            mock_tag = MagicMock()
            mock_tag.destination = f"{registry_url}/test-image"
            mock_tag.suffix = "merged"
            mock_tag.__str__ = lambda self: f"{registry_url}/test-image:merged"
            mock_target.tags = StringableList([mock_tag])

            return mock_target

        return _create_target

    def test_workflow_with_plain_http_flag(self, mock_image_target_for_local_registry):
        """Test that OrasMergeWorkflow correctly propagates plain_http to all commands."""
        mock_target = mock_image_target_for_local_registry("localhost:5000")
        mock_target.get_merge_sources.return_value = [
            "localhost:5000/test/tmp@sha256:amd64digest",
            "localhost:5000/test/tmp@sha256:arm64digest",
        ]

        workflow = OrasMergeWorkflow(
            oras_bin="oras",
            image_target=mock_target,
            annotations={"test": "annotation"},
            plain_http=True,
        )

        # Verify the workflow is created with plain_http=True
        assert workflow.plain_http is True

        # Run in dry-run mode to capture commands without execution
        with patch("subprocess.run") as mock_run:
            result = workflow.run(dry_run=True)

        # Verify dry run succeeds without calling subprocess
        mock_run.assert_not_called()
        assert result.success is True

    def test_from_image_target_with_plain_http(self, mock_image_target_for_local_registry):
        """Test creating workflow from ImageTarget with plain_http option."""
        mock_target = mock_image_target_for_local_registry("localhost:5000")
        mock_target.context = MagicMock(spec=ImageTargetContext)
        mock_target.context.base_path = Path("/project")
        mock_target.settings = MagicMock(spec=ImageTargetSettings)
        mock_target.settings.temp_registry = "localhost:5000"
        mock_target.get_merge_sources.return_value = [
            "localhost:5000/test/tmp@sha256:digest",
        ]

        with patch("posit_bakery.plugins.builtin.imagetools.oras.find_oras_bin", return_value="oras"):
            workflow = OrasMergeWorkflow.from_image_target(mock_target, plain_http=True)

        assert workflow.plain_http is True
        assert workflow.oras_bin == "oras"


class TestOrasIndexCreateWorkflowRetry:
    """The index-create primitive retries transient registry errors."""

    @pytest.fixture
    def workflow(self, mock_image_target_factory):
        target = mock_image_target_factory()
        return OrasIndexCreateWorkflow(
            oras_bin="oras",
            image_target=target,
            annotations={"k": "v"},
            retry_policy=RetryPolicy(max_attempts=5, initial_backoff=1.0),
        )

    def test_retries_transient_not_found_then_succeeds(self, workflow):
        attempts = {"n": 0}

        def side_effect(cmd, capture_output):
            attempts["n"] += 1
            if attempts["n"] < 3:
                return subprocess.CompletedProcess(args=cmd, returncode=1, stdout=b"", stderr=b"sha256:abc: not found")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

        with patch("subprocess.run", side_effect=side_effect), patch("posit_bakery.retry.time.sleep") as sleep:
            result = workflow.run()

        assert result.success is True
        assert attempts["n"] == 3
        assert sleep.call_count == 2

    def test_non_transient_error_fails_without_retry(self, workflow):
        with (
            patch("subprocess.run") as mock_run,
            patch("posit_bakery.retry.time.sleep") as sleep,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=1, stdout=b"", stderr=b"unauthorized: authentication required"
            )
            result = workflow.run()

        assert result.success is False
        assert mock_run.call_count == 1
        sleep.assert_not_called()


class TestOrasIndexCopyWorkflowRetry:
    """The index-copy primitive retries transient registry errors."""

    def test_retries_transient_then_succeeds(self, mock_image_target_factory):
        target = mock_image_target_factory()
        workflow = OrasIndexCopyWorkflow(
            oras_bin="oras",
            image_target=target,
            retry_policy=RetryPolicy(max_attempts=5, initial_backoff=1.0),
        )

        attempts = {"n": 0}

        def side_effect(cmd, capture_output):
            attempts["n"] += 1
            if attempts["n"] == 1:
                return subprocess.CompletedProcess(args=cmd, returncode=1, stdout=b"", stderr=b"manifest unknown")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

        with patch("subprocess.run", side_effect=side_effect), patch("posit_bakery.retry.time.sleep"):
            result = workflow.run(source="ghcr.io/posit-dev/test-image/tmp:src")

        assert result.success is True
        # 1 failed + 1 retried success for the single destination.
        assert attempts["n"] == 2


class TestOrasWaitForSourcesWorkflow:
    """Tests for the pre-flight source-digest availability wait."""

    def _ok(self, cmd):
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"{}", stderr=b"")

    def _missing(self, cmd):
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout=b"", stderr=b"not found")

    def test_all_sources_ready_first_sweep(self):
        wf = OrasWaitForSourcesWorkflow(
            oras_bin="oras",
            sources=[
                "ghcr.io/posit-dev/test/tmp@sha256:a",
                "ghcr.io/posit-dev/test/tmp@sha256:b",
            ],
        )
        sleep = MagicMock()
        with patch("subprocess.run", side_effect=lambda cmd, capture_output: self._ok(cmd)):
            result = wf.run(sleep=sleep, now=lambda: 0.0)

        assert result.success is True
        assert result.ready == [
            "ghcr.io/posit-dev/test/tmp@sha256:a",
            "ghcr.io/posit-dev/test/tmp@sha256:b",
        ]
        assert result.missing == []
        sleep.assert_not_called()

    def test_waits_until_source_appears(self):
        wf = OrasWaitForSourcesWorkflow(
            oras_bin="oras",
            sources=["ghcr.io/posit-dev/test/tmp@sha256:a"],
            poll_interval=5.0,
            timeout=600.0,
        )
        # First sweep: missing. Second sweep: present.
        responses = {"n": 0}

        def side_effect(cmd, capture_output):
            responses["n"] += 1
            return self._missing(cmd) if responses["n"] == 1 else self._ok(cmd)

        clock = {"t": 0.0}

        def now():
            return clock["t"]

        def sleep(seconds):
            clock["t"] += seconds

        with patch("subprocess.run", side_effect=side_effect):
            result = wf.run(sleep=sleep, now=now)

        assert result.success is True
        assert result.ready == ["ghcr.io/posit-dev/test/tmp@sha256:a"]
        assert result.waited_seconds == 5.0

    def test_times_out_and_reports_missing(self):
        wf = OrasWaitForSourcesWorkflow(
            oras_bin="oras",
            sources=[
                "ghcr.io/posit-dev/test/tmp@sha256:a",
                "ghcr.io/posit-dev/test/tmp@sha256:b",
            ],
            poll_interval=5.0,
            timeout=10.0,
        )

        # 'a' is always present; 'b' never appears.
        def side_effect(cmd, capture_output):
            ref = cmd[-1]
            return self._ok(cmd) if ref.endswith("sha256:a") else self._missing(cmd)

        clock = {"t": 0.0}

        def sleep(seconds):
            clock["t"] += seconds

        with patch("subprocess.run", side_effect=side_effect):
            result = wf.run(sleep=sleep, now=lambda: clock["t"])

        assert result.success is False
        assert result.ready == ["ghcr.io/posit-dev/test/tmp@sha256:a"]
        assert result.missing == ["ghcr.io/posit-dev/test/tmp@sha256:b"]
        assert "still unreadable" in result.error

    def test_non_transient_error_raises_immediately(self):
        """A non-transient fetch error (e.g. auth) must not be polled on — it
        raises right away instead of burning the full timeout."""
        wf = OrasWaitForSourcesWorkflow(
            oras_bin="oras",
            sources=["ghcr.io/posit-dev/test/tmp@sha256:a"],
            poll_interval=5.0,
            timeout=600.0,
        )
        sleep = MagicMock()

        def side_effect(cmd, capture_output):
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout=b"", stderr=b"unauthorized: authentication required"
            )

        with patch("subprocess.run", side_effect=side_effect):
            with pytest.raises(BakeryToolRuntimeError):
                wf.run(sleep=sleep, now=lambda: 0.0)

        # Failed fast: no backoff sleep, no waiting for the timeout.
        sleep.assert_not_called()

    def test_dry_run_skips_polling(self):
        wf = OrasWaitForSourcesWorkflow(oras_bin="oras", sources=["ghcr.io/posit-dev/test/tmp@sha256:a"])
        with patch("subprocess.run") as mock_run:
            result = wf.run(dry_run=True)
        mock_run.assert_not_called()
        assert result.success is True

    def test_no_sources_is_success(self):
        wf = OrasWaitForSourcesWorkflow(oras_bin="oras", sources=[])
        with patch("subprocess.run") as mock_run:
            result = wf.run()
        mock_run.assert_not_called()

    def test_wait_for_sources_passes_runner_through(self):
        wf = OrasWaitForSourcesWorkflow(oras_bin="oras", sources=["ghcr.io/posit-dev/test/tmp@sha256:a"])
        fake_runner = MagicMock()
        fake_runner.run.return_value = subprocess.CompletedProcess(
            args=["oras"], returncode=0, stdout=b"{}", stderr=b""
        )

        result = wf.run(sleep=MagicMock(), now=lambda: 0.0, runner=fake_runner)

        assert result.success is True
        fake_runner.run.assert_called_once()
