import textwrap
from typing import List

from posit_bakery.error import BakeryToolRuntimeError

# Exit code meanings applied by TrivySuite's exit-code convention -- Bakery-internal
# sentinels, never trivy's own caller-configured `--exit-code` value (that value is
# recorded separately in each error's `metadata["trivy_exit_code"]`).
TRIVY_EXIT_CODE_SUCCESS = 0
TRIVY_EXIT_CODE_GENERAL_ERROR = 1
TRIVY_EXIT_CODE_SEVERITY_THRESHOLD = 2

TRIVY_EXIT_CODE_DESCRIPTIONS = {
    TRIVY_EXIT_CODE_SUCCESS: "Passed",
    TRIVY_EXIT_CODE_GENERAL_ERROR: "General error (scan failed to produce a report)",
    TRIVY_EXIT_CODE_SEVERITY_THRESHOLD: (
        "Vulnerabilities found at one of the effective failure-severity levels "
        "(the configured `failureSeverity` set, or trivy's own --exit-code when unset)"
    ),
}


class BakeryTrivyError(BakeryToolRuntimeError):
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
        desc = TRIVY_EXIT_CODE_DESCRIPTIONS.get(self.exit_code)
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
