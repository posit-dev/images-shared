import textwrap
from typing import List

from posit_bakery.error import BakeryToolRuntimeError

# Bakery-internal exit-code sentinels recorded on errors (oscap's own code is kept in metadata).
OPENSCAP_EXIT_CODE_GENERAL_ERROR = 1
OPENSCAP_EXIT_CODE_GATE_BREACH = 2

OPENSCAP_EXIT_CODE_DESCRIPTIONS = {
    OPENSCAP_EXIT_CODE_GENERAL_ERROR: "Scan failed or its results did not pass validation",
    OPENSCAP_EXIT_CODE_GATE_BREACH: "Failing rules at or above the configured `failOn` severity",
}


class BakeryOpenSCAPContentError(Exception):
    """SCAP content could not be downloaded, verified or resolved."""


class BakeryOpenSCAPError(BakeryToolRuntimeError):
    def __init__(
        self,
        message: str = "",
        tool_name: str = "openscap",
        cmd: List[str] | None = None,
        stdout: str | bytes | None = None,
        stderr: str | bytes | None = None,
        exit_code: int = OPENSCAP_EXIT_CODE_GENERAL_ERROR,
        metadata: dict | None = None,
    ) -> None:
        super().__init__(
            message=message,
            tool_name=tool_name,
            cmd=cmd or [],
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            metadata=metadata,
        )

    def __str__(self) -> str:
        s = f"{self.message}\n"
        s += f"  - Exit code: {self.exit_code}"
        desc = OPENSCAP_EXIT_CODE_DESCRIPTIONS.get(self.exit_code)
        if desc:
            s += f" ({desc})"
        s += "\n"
        stdout_dump = self.dump_stdout()
        if stdout_dump:
            s += f"  - Output:\n{textwrap.indent(stdout_dump, '      ')}\n"
        if self.cmd:
            s += f"  - Command executed: {' '.join(self.cmd)}\n"
        if self.metadata:
            s += "  - Metadata:\n"
            for key, value in self.metadata.items():
                s += f"    - {key}: {value}\n"
        return s
