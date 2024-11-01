import os
import subprocess
from pathlib import Path
from typing import Dict, List, Union, Tuple

from rich import print

from posit_bakery.error import BakeryGossError, BakeryFileNotFoundError
from posit_bakery.parser.config import Config
from posit_bakery.parser.manifest import Manifest, TargetBuild


class DGossManager:
    def __init__(
        self,
        context: Union[str, bytes, os.PathLike],
        config: Config,
        manifests: Dict[str, Manifest],
        runtime_options: List[str] = None,
    ) -> None:
        # Context is the root directory of the project where config.toml exists
        self.context: Path = Path(context)
        if not self.context.exists():
            raise BakeryFileNotFoundError(f"Context directory {self.context} does not exist.")

        # The project Config for the images being tested
        self.config: Config = config

        # List of Manifests being tested
        self.manifests: List[Manifest] = []

        # Optional list of runtime options provided by user for dgoss
        self.runtime_options: List[str] = runtime_options

        # A list of dgoss environment variables/command pairs to be executed
        self.dgoss_commands: List[Tuple[Dict[str, str], List[str]]] = []
        for manifest_name, manifest in manifests.items():
            self.add_manifest(manifest)

    def exec(self) -> None:
        """Executes the current list of dgoss commands"""
        for run_env, cmd in self.dgoss_commands:
            relevant_environment = {
                k: v for k, v in run_env.items() if k in ["GOSS_PATH", "GOSS_FILES_PATH", "GOSS_SLEEP"]
            }
            print(f"Environment: {relevant_environment}")
            print(f"Running dgoss command: {' '.join(cmd)}")
            p = subprocess.run(cmd, env=run_env)
            if p.returncode != 0:
                raise BakeryGossError(f"Goss exited with code {p.returncode}", exit_code=p.returncode)

    def add_manifest(self, manifest: Manifest):
        """Adds a manifest to the list of manifests to be tested and renders appropriate dgoss commands
        for each target build

        :param manifest: The manifest to be added
        """
        for target_build in manifest.target_builds:
            run_env, cmd = self.__construct_dgoss_command(target_build)
            self.dgoss_commands.append((run_env, cmd))
        self.manifests.append(manifest)

    def __construct_dgoss_command(self, target_build: TargetBuild) -> (Dict[str, str], List[str]):
        # Copy the current environment variables and assume they should be used
        run_env = os.environ.copy()

        # Check if dgoss is installed and set the path
        # TODO: Add support for in PATH dgoss
        dgoss_path = self.context / "tools" / "dgoss"
        if "DGOSS_PATH" in run_env:
            dgoss_path = Path(run_env["DGOSS_PATH"])
        if not dgoss_path.exists():
            raise BakeryGossError(
                f"Unable to find dgoss at {dgoss_path}. "
                f"Run `just install-goss` or specify 'DGOSS_PATH' as an environment variable."
            )

        # Construct the base dgoss command
        cmd = [str(dgoss_path), "run"]

        # Check if goss is installed and set the path
        # TODO: Add support for in PATH goss
        if "GOSS_PATH" not in run_env:
            goss_tools_path = self.context / "tools" / "goss"
            if not goss_tools_path.exists():
                raise BakeryGossError(
                    f"Unable to find goss tools at {goss_tools_path}. "
                    f"Run `just install-goss` or specify 'GOSS_PATH' as an environment variable."
                )
            run_env["GOSS_PATH"] = str(goss_tools_path)

        # Check if goss test path is defined and set the path to it
        goss_test_path = target_build.goss_test_path
        if goss_test_path is None:
            raise BakeryGossError(
                "Path to Goss test directory must be defined or left empty for default. Please check the manifest.toml."
            )
        if not goss_test_path.is_absolute():
            # Create an absolute path to tests if not already provided
            goss_test_path = self.context / goss_test_path
        if not goss_test_path.exists():
            raise BakeryGossError(
                f"Unable to find goss test files at {target_build.goss_test_path}. "
                f"Run `just install-goss` or specify 'GOSS_FILES_PATH' as an environment variable."
            )
        # Set path to goss test files
        run_env["GOSS_FILES_PATH"] = goss_test_path

        # Check if goss deps path is defined and set the path to it
        if target_build.goss_deps is not None:
            goss_deps = target_build.goss_deps
            if not goss_deps.is_absolute():
                goss_deps = self.context / goss_deps
            if goss_deps.exists():
                cmd.append(f"--mount=type=bind,source={str(goss_deps)},destination=/tmp/deps")
            else:
                print(
                    f"[bright_yellow][bold]WARNING:[/bold] "
                    f"Skipping mounting of goss deps directory {goss_deps} as it does not exist."
                )

        # Check if goss wait time is defined and set the sleep time prior to running goss tests
        if target_build.goss_wait is not None:
            run_env["GOSS_SLEEP"] = str(target_build.goss_wait)

        # Check if build type is defined and set the image type
        if target_build.type is not None:
            cmd.extend(["-e", f"IMAGE_TYPE={target_build.type}"])

        # Add user runtime options if provided
        if self.runtime_options:
            cmd.extend(self.runtime_options)

        # Append the target image tag, assuming the first one is valid to use and no duplications exist
        cmd.append(target_build.render_fq_tags(self.config.get_registry_base_urls()[0])[0])

        # Append the goss command to run or use the default `sleep infinity`
        cmd.extend(target_build.goss_command.split() or ["sleep", "infinity"])

        return run_env, cmd
