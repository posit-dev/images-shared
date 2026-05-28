"""SOCI CLI integration module."""

import logging
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field

from posit_bakery.error import BakeryToolRuntimeError
from posit_bakery.util import find_bin

log = logging.getLogger(__name__)


def find_soci_bin(context: Path) -> str:
    """Resolve a path or PATH-resident name for the soci binary.

    :param context: Project context to search for the binary in.
    :return: Path to the soci binary, or the bare name "soci" when it
        resolves through PATH.
    :raises BakeryToolNotFoundError: If soci cannot be found.
    """
    return find_bin(context, "soci", "SOCI_PATH") or "soci"


class SociCommand(BaseModel, ABC):
    """Base class for soci CLI invocations."""

    soci_bin: Annotated[str, Field(description="Path to the soci binary.")]
    containerd_address: Annotated[
        str | None,
        Field(default=None, description="containerd GRPC address. None => soci default."),
    ]
    containerd_namespace: Annotated[
        str,
        Field(default="default", description="containerd namespace for commands."),
    ]
    standalone: Annotated[
        bool,
        Field(default=False, description="Run without containerd (file-to-file mode)."),
    ]

    @property
    @abstractmethod
    def command(self) -> list[str]:
        """Return the full command to execute."""
        ...

    def run(self, dry_run: bool = False) -> subprocess.CompletedProcess:
        """Execute the soci command.

        :param dry_run: If True, log the command without executing it.
        :return: The completed process result.
        :raises BakeryToolRuntimeError: On non-zero exit.
        """
        cmd = self.command
        log.debug(f"Executing soci command: {' '.join(cmd)}")

        if dry_run:
            log.info(f"[DRY RUN] Would execute: {' '.join(cmd)}")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            raise BakeryToolRuntimeError(
                message="soci command failed",
                tool_name="soci",
                cmd=cmd,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
            )

        return result
