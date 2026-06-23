import textwrap
from typing import List

from posit_bakery.error import BakeryToolRuntimeError


class BakeryDGossError(BakeryToolRuntimeError):
    def __init__(
        self,
        message: str = None,
        tool_name: str = None,
        cmd: List[str] = None,
        stdout: str | bytes | None = None,
        stderr: str | bytes | None = None,
        exit_code: int = 1,
        parse_error: Exception = None,
        metadata: dict | None = None,
    ) -> None:
        super().__init__(
            message=message,
            tool_name=tool_name,
            cmd=cmd,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            metadata=metadata,
        )
        self.parse_error = parse_error

    def __str__(self) -> str:
        s = f"{self.message}\n"
        s += f"  - Exit code: {self.exit_code}\n"
        stdout_dump = self.dump_stdout()
        if stdout_dump:
            s += f"  - Command output:\n{textwrap.indent(stdout_dump, '      ')}\n"
        stderr_dump = self.dump_stderr(lines=50)
        if stderr_dump:
            s += f"  - Error output:\n{textwrap.indent(stderr_dump, '      ')}\n"
        s += f"  - Command executed: {' '.join(self.cmd)}\n"
        if self.metadata:
            s += "  - Metadata:\n"
            for key, value in self.metadata.items():
                s += f"    - {key}: {value}\n"
        return s
