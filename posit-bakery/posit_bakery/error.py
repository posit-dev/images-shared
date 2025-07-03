import os
import textwrap
from typing import Union, List

import pydantic


class BakeryError(Exception):
    """Base class for all Bakery exceptions"""

    pass


class BakeryConfigError(BakeryError):
    """Error for config/manifest issues"""

    pass


class BakeryModelValidationError(BakeryConfigError):
    """Error for model validation issues"""

    def __init__(
        self,
        model_name: str = None,
        filepath: Union[str, bytes, os.PathLike] = None,
    ) -> None:
        super().__init__(f"Validation error(s) occurred when loading '{model_name}' data.")
        self.model_name = model_name
        self.filepath = filepath
        self.add_note(f"Filepath: {filepath}")

    def __str__(self) -> str:
        s = str(self.__cause__)
        s += "\n\n"
        s += super().__str__() + "\n"
        for note in self.__notes__:
            s += textwrap.indent(note, "  ")
            s += "\n"
        if isinstance(self.__cause__, pydantic.ValidationError):
            s += textwrap.indent(f"Error count: {self.__cause__.error_count()}", "  ")
            s += "\n"
        s += "\n"

        return s


class BakeryModelValidationErrorGroup(ExceptionGroup):
    """Group of model validation errors"""

    def __str__(self) -> str:
        s = ""
        affected_files = []
        total_errors = 0
        for e in self.exceptions:
            if e.filepath not in affected_files:
                affected_files.append(e.filepath)
            if isinstance(self.__cause__, pydantic.ValidationError):
                total_errors += e.__cause__.error_count()
            s += str(e)
            s += "-" * 80
            s += "\n\n"

        s += f"Total errors: {total_errors}\n"
        s += f"Affected files: \n"
        for f in affected_files:
            s += f"  - {f}\n"
        s += "\n"

        return s


class BakeryImageNotFoundError(BakeryConfigError):
    """Error for an expected image not being found"""

    pass


class BakeryImageError(BakeryConfigError):
    """Error for an image being malformed or invalid"""

    pass


class BakeryTemplatingError(BakeryError):
    """Error for template rendering issues"""

    pass


class BakeryFileError(BakeryError):
    """Generic error for file/directory issues"""

    def __init__(
        self,
        message: str = None,
        filepath: Union[str, bytes, os.PathLike] | List[Union[str, bytes, os.PathLike]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.filepath = filepath

        if filepath:
            filepath_note = f"Expected filepath(s): "
            if isinstance(filepath, (str, bytes, os.PathLike)):
                filepath_note += f"  - {filepath}\n"
            elif isinstance(filepath, list):
                for f in filepath:
                    filepath_note += f"  - {f}\n"
            self.add_note(filepath_note)


class BakeryToolError(BakeryError):
    """Generic error for external tool issues"""

    def __init__(self, message: str = None, tool_name: str = None) -> None:
        super().__init__(message)
        self.message = message
        self.tool_name = tool_name


class BakeryToolNotFoundError(BakeryToolError):
    """Error for an expected tool not being found"""

    pass


class BakeryToolRuntimeError(BakeryToolError):
    def __init__(
        self,
        message: str = None,
        tool_name: str = None,
        cmd: List[str] = None,
        stdout: str | bytes | None = None,
        stderr: str | bytes | None = None,
        exit_code: int = 1,
        metadata: dict | None = None,
    ) -> None:
        super().__init__(message, tool_name)
        self.exit_code = exit_code
        self.cmd = cmd
        self.stdout = stdout
        self.stderr = stderr
        self.metadata = metadata

    def dump_stdout(self, lines: int = 10) -> str:
        if not self.stdout:
            return ""
        if isinstance(self.stdout, bytes):
            return "\n".join(self.stdout.decode().splitlines()[:lines])
        else:
            return "\n".join(self.stdout.splitlines()[:lines])

    def dump_stderr(self, lines: int = 10) -> str:
        if not self.stderr:
            return ""
        if isinstance(self.stderr, bytes):
            return "\n".join(self.stderr.decode().splitlines()[:lines])
        else:
            return "\n".join(self.stderr.splitlines()[:lines])

    def __str__(self) -> str:
        s = f"{self.message}'\n"
        s += f"  - Exit code: {self.exit_code}\n"
        s += f"  - Command executed: {' '.join(self.cmd)}\n"
        if self.metadata:
            s += "  - Metadata:\n"
            for key, value in self.metadata.items():
                s += f"    - {key}: {value}\n"
        return s


class BakeryToolRuntimeErrorGroup(ExceptionGroup):
    """Group of tool runtime errors"""

    def __str__(self) -> str:
        s = f""
        for e in self.exceptions:
            s += f"{e.message}\n"
            s += f"  - Command executed: '{' '.join(e.cmd)}'\n"
            if e.metadata:
                s += "  - Metadata:\n"
                for key, value in e.metadata.items():
                    s += f"    - {key}: {value}\n"
            s += "\n"
        s += "\n"
        s += f"{len(self.exceptions)} command(s) returned errors\n"

        return s
