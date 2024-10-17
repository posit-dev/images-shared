import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Any

from rich import print

from posit_bakery.bake.plan import BakePlan
from posit_bakery.error import BakeryFileNotFoundError, BakeryGossError
from posit_bakery.parser.config import Config
from posit_bakery.parser.manifest import Manifest, TargetBuild


class DGossManager:
    def __init__(
            self,
            context: Path,
            config: Config,
            manifests: List[Manifest],
            runtime_options: List[str] = None,
    ):
        self.context = context
        self.config = config
        self.manifests = []
        self.commands = []
        self.runtime_options = runtime_options
        self.dgoss_commands = []
        for manifest in manifests:
            self.add_manifest(manifest)

    def exec(self):
        for run_env, cmd in self.dgoss_commands:
            relevant_environment = {
                k: v for k, v in run_env.items() if k in ["GOSS_PATH", "GOSS_FILES_PATH", "GOSS_SLEEP"]
            }
            print(f"Environment: {relevant_environment}")
            print(f"Running dgoss command: {' '.join(cmd)}")
            p = subprocess.run(cmd, env=run_env)
            if p.returncode != 0:
                raise BakeryGossError(f"Goss exited with code {p.returncode}", exit_code=p.returncode)

    def construct_dgoss_command(self, target_build: TargetBuild) -> (Dict[str, str], List[str]):
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

        if target_build.goss_test_path is None or not target_build.goss_test_path.exists():
            raise BakeryGossError(
                f"Unable to find goss test files at {target_build.goss_test_path}. "
                f"Run `just install-goss` or specify 'GOSS_FILES_PATH' as an environment variable."
            )
        run_env["GOSS_FILES_PATH"] = target_build.goss_test_path

        if target_build.goss_deps is not None and target_build.goss_deps.exists():
            cmd.append(f"--mount=type=bind,source={str(target_build.goss_deps)},destination=/tmp/deps")

        if target_build.goss_wait is not None:
            run_env["GOSS_SLEEP"] = target_build.goss_wait

        if target_build.type is not None:
            cmd.extend(["-e", f"IMAGE_TYPE={target_build.type}"])

        if self.runtime_options:
            cmd.extend(self.runtime_options)

        cmd.append(target_build.render_fq_tags(self.config.get_registry_base_urls()[0])[0])

        cmd.extend(target_build.goss_command.split() or ["sleep", "infinity"])

        return run_env, cmd

    def add_manifest(self, manifest: Manifest):
        self.manifests.append(manifest)
        for target_build in manifest.target_builds:
            run_env, cmd = self.construct_dgoss_command(target_build)
            self.dgoss_commands.append((run_env, cmd))
