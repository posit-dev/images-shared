import textwrap
from typing import List

from posit_bakery.error import BakeryToolRuntimeError

# Exit code meanings for wizcli scan container-image
WIZCLI_EXIT_CODE_SUCCESS = 0
WIZCLI_EXIT_CODE_GENERAL_ERROR = 1
WIZCLI_EXIT_CODE_INVALID_COMMAND = 2
WIZCLI_EXIT_CODE_AUTH_ERROR = 3
WIZCLI_EXIT_CODE_POLICY_VIOLATION = 4

WIZCLI_EXIT_CODE_DESCRIPTIONS = {
    WIZCLI_EXIT_CODE_SUCCESS: "Passed",
    WIZCLI_EXIT_CODE_GENERAL_ERROR: "General error (timeout, network)",
    WIZCLI_EXIT_CODE_INVALID_COMMAND: "Invalid command (bad syntax or parameters)",
    WIZCLI_EXIT_CODE_AUTH_ERROR: "Authentication error",
    WIZCLI_EXIT_CODE_POLICY_VIOLATION: "Security issues violate policy",
}


class BakeryWizCLIError(BakeryToolRuntimeError):
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
        super().__init__(
            message=message,
            tool_name=tool_name,
            cmd=cmd,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            metadata=metadata,
        )

    def __str__(self) -> str:
        s = f"{self.message}\n"
        s += f"  - Exit code: {self.exit_code}"
        desc = WIZCLI_EXIT_CODE_DESCRIPTIONS.get(self.exit_code)
        if desc:
            s += f" ({desc})"
        s += "\n"
        stdout_dump = self.dump_stdout()
        if stdout_dump:
            s += f"  - Output:\n{textwrap.indent(stdout_dump, '      ')}\n"
        s += f"  - Command executed: {' '.join(self.cmd)}\n"
        if self.metadata:
            s += "  - Metadata:\n"
            for key, value in self.metadata.items():
                s += f"    - {key}: {value}\n"
        return s
