"""Tests for posit_bakery.error module.

These tests cover the exception classes and their string representations.
"""

from pathlib import Path

import pytest
from jinja2 import TemplateSyntaxError, UndefinedError

from posit_bakery.error import (
    BakeryError,
    BakeryTemplateError,
    BakeryRenderError,
    BakeryRenderErrorGroup,
    BakeryFileError,
    BakeryToolError,
    BakeryToolNotFoundError,
    BakeryToolRuntimeError,
    BakeryDGossError,
    BakeryToolRuntimeErrorGroup,
    BakeryBuildErrorGroup,
)


pytestmark = [pytest.mark.unit]


class TestBakeryError:
    def test_base_exception(self):
        """Test that BakeryError can be instantiated and raised."""
        err = BakeryError("Test error message")
        assert str(err) == "Test error message"
        assert isinstance(err, Exception)

    def test_raise_and_catch(self):
        """Test that BakeryError can be raised and caught."""
        with pytest.raises(BakeryError, match="Test error"):
            raise BakeryError("Test error")


class TestBakeryTemplateError:
    def test_template_error(self):
        """Test that BakeryTemplateError can be instantiated."""
        err = BakeryTemplateError("Template syntax problem")
        assert str(err) == "Template syntax problem"
        assert isinstance(err, BakeryError)


class TestBakeryRenderError:
    def test_basic_render_error(self):
        """Test BakeryRenderError with minimal parameters."""
        cause = BakeryTemplateError("undefined variable 'foo'")
        err = BakeryRenderError(cause=cause)
        result = str(err)
        assert "Error rendering template" in result
        assert "undefined variable 'foo'" in result

    def test_render_error_with_template_path(self):
        """Test BakeryRenderError includes template path."""
        context = Path("/project")
        template = Path("/project/image/template/Containerfile.jinja2")
        cause = BakeryTemplateError("missing variable")
        err = BakeryRenderError(cause=cause, context=context, template=template)
        result = str(err)
        assert "image/template/Containerfile.jinja2" in result

    def test_render_error_with_jinja_lineno(self):
        """Test BakeryRenderError shows line number from Jinja2 errors."""
        cause = TemplateSyntaxError("unexpected end of template", lineno=42)
        context = Path("/project")
        template = Path("/project/template.jinja2")
        err = BakeryRenderError(cause=cause, context=context, template=template)
        result = str(err)
        assert "line 42" in result

    def test_render_error_with_all_metadata(self):
        """Test BakeryRenderError with all optional metadata."""
        context = Path("/project")
        cause = UndefinedError("'foo' is undefined")
        err = BakeryRenderError(
            cause=cause,
            context=context,
            image="my-image",
            version="1.0.0",
            variant="Standard",
            template=Path("/project/tpl/file.jinja2"),
            destination=Path("/project/out/file"),
        )
        result = str(err)
        assert "Image: my-image" in result
        assert "Version: 1.0.0" in result
        assert "Variant: Standard" in result
        assert "Destination:" in result

    def test_render_error_stores_cause(self):
        """Test that BakeryRenderError properly chains the cause."""
        cause = BakeryTemplateError("original error")
        err = BakeryRenderError(cause=cause)
        assert err.__cause__ is cause


class TestBakeryRenderErrorGroup:
    def test_render_error_group_str(self):
        """Test BakeryRenderErrorGroup string representation."""
        errors = [
            BakeryRenderError(cause=BakeryTemplateError("error 1")),
            BakeryRenderError(cause=BakeryTemplateError("error 2")),
            BakeryRenderError(cause=BakeryTemplateError("error 3")),
        ]
        group = BakeryRenderErrorGroup("Multiple render errors", errors)
        result = str(group)
        assert "error 1" in result
        assert "error 2" in result
        assert "error 3" in result
        assert "3 template(s) returned errors" in result


class TestBakeryFileError:
    def test_file_error_message_only(self):
        """Test BakeryFileError with just a message."""
        err = BakeryFileError("File not found")
        assert str(err) == "File not found"
        assert err.filepath is None

    def test_file_error_with_single_filepath(self):
        """Test BakeryFileError with a single filepath."""
        err = BakeryFileError("File not found", filepath="/path/to/file.txt")
        assert err.message == "File not found"
        assert err.filepath == "/path/to/file.txt"
        # Check that the note was added
        notes = err.__notes__
        assert len(notes) == 1
        assert "/path/to/file.txt" in notes[0]

    def test_file_error_with_path_object(self):
        """Test BakeryFileError with a Path object."""
        filepath = Path("/project/missing/file.yaml")
        err = BakeryFileError("Config file missing", filepath=filepath)
        assert err.filepath == filepath
        notes = err.__notes__
        assert str(filepath) in notes[0]

    def test_file_error_with_multiple_filepaths(self):
        """Test BakeryFileError with a list of filepaths."""
        filepaths = ["/path/one.txt", "/path/two.txt", Path("/path/three.txt")]
        err = BakeryFileError("Multiple files missing", filepath=filepaths)
        assert err.filepath == filepaths
        notes = err.__notes__
        assert "/path/one.txt" in notes[0]
        assert "/path/two.txt" in notes[0]
        assert "/path/three.txt" in notes[0]


class TestBakeryToolError:
    def test_tool_error_basic(self):
        """Test BakeryToolError with message and tool name."""
        err = BakeryToolError("Docker failed", tool_name="docker")
        assert str(err) == "Docker failed"
        assert err.tool_name == "docker"

    def test_tool_error_message_only(self):
        """Test BakeryToolError with just a message."""
        err = BakeryToolError("Something went wrong")
        assert err.tool_name is None


class TestBakeryToolNotFoundError:
    def test_tool_not_found(self):
        """Test BakeryToolNotFoundError."""
        err = BakeryToolNotFoundError("goss not found in PATH", tool_name="goss")
        assert "goss not found" in str(err)
        assert err.tool_name == "goss"
        assert isinstance(err, BakeryToolError)


class TestBakeryToolRuntimeError:
    def test_runtime_error_basic(self):
        """Test BakeryToolRuntimeError with basic parameters."""
        err = BakeryToolRuntimeError(
            message="Build failed",
            tool_name="docker",
            cmd=["docker", "build", "."],
            exit_code=1,
        )
        result = str(err)
        assert "Build failed" in result
        assert "Exit code: 1" in result
        assert "docker build ." in result

    def test_runtime_error_with_metadata(self):
        """Test BakeryToolRuntimeError with metadata."""
        err = BakeryToolRuntimeError(
            message="Build failed",
            tool_name="docker",
            cmd=["docker", "build", "."],
            exit_code=1,
            metadata={"image": "my-image", "tag": "latest"},
        )
        result = str(err)
        assert "Metadata:" in result
        assert "image: my-image" in result
        assert "tag: latest" in result

    def test_dump_stdout_string(self):
        """Test dump_stdout with string output."""
        err = BakeryToolRuntimeError(
            message="Error",
            cmd=["cmd"],
            stdout="line1\nline2\nline3\nline4\nline5",
        )
        result = err.dump_stdout(lines=3)
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result
        assert "line4" not in result

    def test_dump_stdout_bytes(self):
        """Test dump_stdout with bytes output."""
        err = BakeryToolRuntimeError(
            message="Error",
            cmd=["cmd"],
            stdout=b"line1\nline2\nline3",
        )
        result = err.dump_stdout(lines=2)
        assert "line1" in result
        assert "line2" in result
        assert "line3" not in result

    def test_dump_stdout_empty(self):
        """Test dump_stdout with no output."""
        err = BakeryToolRuntimeError(message="Error", cmd=["cmd"], stdout=None)
        assert err.dump_stdout() == ""

    def test_dump_stderr_string(self):
        """Test dump_stderr with string output."""
        err = BakeryToolRuntimeError(
            message="Error",
            cmd=["cmd"],
            stderr="error1\nerror2\nerror3",
        )
        result = err.dump_stderr(lines=2)
        assert "error1" in result
        assert "error2" in result
        assert "error3" not in result

    def test_dump_stderr_bytes(self):
        """Test dump_stderr with bytes output."""
        err = BakeryToolRuntimeError(
            message="Error",
            cmd=["cmd"],
            stderr=b"error line 1\nerror line 2",
        )
        result = err.dump_stderr()
        assert "error line 1" in result
        assert "error line 2" in result

    def test_dump_stderr_empty(self):
        """Test dump_stderr with no output."""
        err = BakeryToolRuntimeError(message="Error", cmd=["cmd"], stderr=None)
        assert err.dump_stderr() == ""


class TestBakeryDGossError:
    def test_dgoss_error_basic(self):
        """Test BakeryDGossError basic functionality."""
        err = BakeryDGossError(
            message="goss tests failed",
            tool_name="dgoss",
            cmd=["dgoss", "run", "my-image"],
            stdout="FAIL - some test",
            exit_code=1,
        )
        result = str(err)
        assert "goss tests failed" in result
        assert "Exit code: 1" in result
        assert "FAIL - some test" in result
        assert "dgoss run my-image" in result

    def test_dgoss_error_with_parse_error(self):
        """Test BakeryDGossError stores parse_error."""
        parse_err = ValueError("Invalid JSON")
        err = BakeryDGossError(
            message="Failed to parse goss output",
            tool_name="dgoss",
            cmd=["dgoss", "run", "img"],
            parse_error=parse_err,
            exit_code=1,
        )
        assert err.parse_error is parse_err

    def test_dgoss_error_with_metadata(self):
        """Test BakeryDGossError with metadata."""
        err = BakeryDGossError(
            message="goss failed",
            tool_name="dgoss",
            cmd=["dgoss", "run", "img"],
            exit_code=1,
            metadata={"image": "test-image", "version": "1.0.0"},
        )
        result = str(err)
        assert "Metadata:" in result
        assert "image: test-image" in result
        assert "version: 1.0.0" in result


class TestBakeryToolRuntimeErrorGroup:
    def test_tool_runtime_error_group_str(self):
        """Test BakeryToolRuntimeErrorGroup string representation."""
        errors = [
            BakeryToolRuntimeError(message="Error 1", cmd=["cmd1"], exit_code=1),
            BakeryToolRuntimeError(message="Error 2", cmd=["cmd2"], exit_code=2),
        ]
        group = BakeryToolRuntimeErrorGroup("Multiple tool errors", errors)
        result = str(group)
        assert "Error 1" in result
        assert "Error 2" in result
        assert "2 command(s) returned errors" in result


class TestBakeryBuildErrorGroup:
    def test_build_error_group_str(self):
        """Test BakeryBuildErrorGroup string representation."""
        errors = [
            BakeryToolRuntimeError(
                message="Build failed for image-a",
                cmd=["docker", "build", "-t", "image-a", "."],
                exit_code=1,
                metadata={"image": "image-a"},
            ),
            BakeryToolRuntimeError(
                message="Build failed for image-b",
                cmd=["docker", "build", "-t", "image-b", "."],
                exit_code=1,
            ),
        ]
        group = BakeryBuildErrorGroup("Build errors", errors)
        result = str(group)
        assert "Build failed for image-a" in result
        assert "Build failed for image-b" in result
        assert "docker build -t image-a ." in result
        assert "docker build -t image-b ." in result
        assert "image: image-a" in result
        assert "2 build(s) returned errors" in result

    def test_build_error_group_with_non_runtime_errors(self):
        """Test BakeryBuildErrorGroup handles mixed error types."""
        errors = [
            BakeryToolRuntimeError(
                message="Runtime error",
                cmd=["docker", "build", "."],
                exit_code=1,
            ),
            BakeryToolError(message="Generic tool error", tool_name="docker"),
        ]
        group = BakeryBuildErrorGroup("Mixed errors", errors)
        result = str(group)
        assert "Runtime error" in result
        assert "Generic tool error" in result
        assert "2 build(s) returned errors" in result
