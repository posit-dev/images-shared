import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Any

from rich import print

from posit_bakery.error import BakeryFileNotFoundError, BakeryGossError


class DGossManager:
    def __init__(
            self,
            context: Path,
            plan: Dict[str, Dict],
            image_version: str = None,
            skip: List[str] = None,
            runtime_options: List[str] = None,
    ):
        self.context = context
        self.plan = plan
        self.image_version = image_version
        self.skip = []
        if skip is not None:
            self.skip = [re.compile(s) for s in skip]
        self.runtime_options = runtime_options
        self.dgoss_commands = []
        self.generate_dgoss_commands()

    def exec(self):
        for run_env, cmd in self.dgoss_commands:
            print(f"Running dgoss command: {' '.join(cmd)}")
            p = subprocess.run(cmd, env=run_env)
            if p.returncode != 0:
                raise BakeryGossError(f"Command failed with exit code {p.returncode}")

    def construct_dgoss_command(self, target_name: str, target_spec: Dict[str, Any]) -> (Dict[str, str], List[str]):
        run_env = os.environ.copy()

        dgoss_path = self.context / "tools" / "dgoss"
        if "DGOSS_PATH" in run_env:
            dgoss_path = Path(run_env["DGOSS_PATH"])
        if not dgoss_path.exists():
            raise BakeryGossError(
                f"Unable to find dgoss at {dgoss_path}. "
                f"Run `just install-goss` or specify 'DGOSS_PATH' as an environment variable."
            )

        cmd = [str(dgoss_path), "run"]

        if "GOSS_PATH" not in run_env:
            goss_tools_path = self.context / "tools" / "goss"
            if not goss_tools_path.exists():
                raise BakeryGossError(
                    f"Unable to find goss tools at {goss_tools_path}. "
                    f"Run `just install-goss` or specify 'GOSS_PATH' as an environment variable."
                )
            run_env["GOSS_PATH"] = str(goss_tools_path)

        if target_spec["labels"].get("co.posit.internal.goss.test.path") is None:
            raise BakeryFileNotFoundError(f"Missing 'co.posit.internal.goss.test.path' label for target '{target_name}")
        run_env["GOSS_FILES_PATH"] = self.context / target_spec["labels"]["co.posit.internal.goss.test.path"]

        if target_spec["labels"].get("co.posit.internal.goss.test.deps") is not None:
            deps_path = target_spec["labels"].get("co.posit.internal.goss.test.deps")
            cmd.append(f"--mount=type=bind,source={str(self.context / deps_path)},destination=/tmp/deps")

        if target_spec["labels"].get("co.posit.internal.goss.test.wait") is not None:
            run_env["GOSS_SLEEP"] = target_spec["labels"]["co.posit.internal.goss.test.wait"]

        if target_spec["labels"].get("co.posit.image.type") is not None:
            cmd.extend(["-e", f"IMAGE_TYPE={target_spec['labels']['co.posit.image.type']}"])

        if self.runtime_options:
            cmd.extend(self.runtime_options)

        cmd.append(target_spec["tags"][0])

        cmd.extend(target_spec["labels"].get("co.posit.internal.goss.test.command", "sleep infinity").split(" "))

        return run_env, cmd

    def generate_dgoss_commands(self):
        for target_name, target_spec in self.plan["target"].items():
            if any(re.search(pattern, target_name) is not None for pattern in self.skip):
                continue
            if self.image_version is None or self.image_version == target_spec["labels"].get("co.posit.image.version"):
                run_env, cmd = self.construct_dgoss_command(target_name, target_spec)
                self.dgoss_commands.append((run_env, cmd))
        if not self.dgoss_commands:
            raise BakeryGossError("No targets found to test")
