import textwrap
from typing import List

from posit_bakery.error import BakeryToolRuntimeError


class BakeryHadolintError(BakeryToolRuntimeError):
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
        s += f"  - Command output: \n{textwrap.indent(self.dump_stdout(), '      ')}\n"
        s += f"  - Command executed: {' '.join(self.cmd)}\n"
        if self.metadata:
            s += "  - Metadata:\n"
            for key, value in self.metadata.items():
                s += f"    - {key}: {value}\n"
        return s
