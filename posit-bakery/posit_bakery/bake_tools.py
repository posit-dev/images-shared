import json
import os
import subprocess
from pathlib import Path
from typing import List, Dict

import git
from rich import print
import typer

from posit_bakery.error import BakeryPlanError, BakeryFileNotFoundError, BakeryBuildError


class BakeManager:
    DOCKER_BAKE_OVERRIDE_HCL_FILE = "docker-bake.override.hcl"
    DOCKER_BAKE_HCL_FILE = "docker-bake.hcl"
    DOCKER_BAKE_MATRIX_HCL_FILE = "docker-bake.matrix.hcl"

    def __init__(self, context: Path, image_name: str = None, bake_files: List[Path] = None, no_override: bool = False):
        self.context = context
        self.bake_files = []
        self._auto_discover_bake_files(image_name, bake_files, no_override)
        print(f"[bright_blue]Bake files found:[/bright_blue] {self.bake_files}")

    def _auto_discover_bake_files_by_image_name(self, image_name: str, no_override: bool = False):
        bake_file = []

        root_bake_file = self.context / self.DOCKER_BAKE_HCL_FILE
        if root_bake_file.exists():
            bake_file.append(root_bake_file)
        else:
            print(
                f"[bright_yellow bold]WARNING:[/bold] Unable to auto-discover a root bake file at {root_bake_file}, "
                f"this may cause unexpected behavior.",
            )

        image_bake_file = self.context / image_name / self.DOCKER_BAKE_HCL_FILE
        if not image_bake_file.exists():
            print(
                f"[bright_red bold]ERROR:[/bold] Unable to auto-discover image bake file expected at {image_bake_file}. "
                f"Exiting...",
            )
            raise BakeryFileNotFoundError(f"Unable to auto-discover image bake file at {image_bake_file}")
        bake_file.append(image_bake_file)

        image_matrix_bake_file = self.context / image_name / self.DOCKER_BAKE_MATRIX_HCL_FILE
        if not image_matrix_bake_file.exists():
            print(
                f"[bright_red bold]ERROR:[/bold] Unable to auto-discover image bake file expected at {image_matrix_bake_file}. "
                f"Exiting...",
            )
            raise BakeryFileNotFoundError(f"Unable to auto-discover image bake file at {image_matrix_bake_file}")
        bake_file.append(image_matrix_bake_file)

        if not no_override:
            root_override_bake_file = self.context / self.DOCKER_BAKE_OVERRIDE_HCL_FILE
            if root_override_bake_file.exists():
                bake_file.append(root_override_bake_file)
            image_override_bake_file = self.context / image_name / self.DOCKER_BAKE_OVERRIDE_HCL_FILE
            if image_override_bake_file.exists():
                bake_file.append(image_override_bake_file)

        return bake_file

    def _auto_discover_bake_files(self, image_name: str = None, bake_files: List[Path] = None, no_override: bool = False):
        if image_name is None and bake_files is None:
            # Full in-context auto-discovery if no options are provided
            self.bake_files = list(self.context.rglob(self.DOCKER_BAKE_HCL_FILE))
            self.bake_files.extend(list(self.context.rglob(self.DOCKER_BAKE_MATRIX_HCL_FILE)))
            if not no_override:
                override_bake_files = list(self.context.rglob(self.DOCKER_BAKE_OVERRIDE_HCL_FILE))
                self.bake_files.extend(override_bake_files)
        elif image_name is not None and bake_files is None:
            # Partial in-context auto-discovery by image name
            self.bake_files = self._auto_discover_bake_files_by_image_name(image_name)
        elif bake_files is not None and image_name is not None:
            # Partial in-context auto-discovery by image name with additional explicit bake files provided
            self.bake_files = list(bake_files)
            self.bake_files.extend(
                x for x in self._auto_discover_bake_files_by_image_name(image_name) if x not in bake_files
            )

        for bake_file in self.bake_files:
            if not bake_file.is_absolute():
                bake_file = self.context / bake_file
            if not bake_file.exists():
                raise BakeryFileNotFoundError(f"Bake file '{bake_file}' does not exist")

    def get_commit_sha(self):
        sha = ""
        try:
            repo = git.Repo(self.context)
            sha = repo.head.object.hexsha
        except Exception as e:
            print(f"[bright_red bold]ERROR:[/bold] Unable to get git commit for labels: {e}")
        return sha

    def plan(self, target: List[str] = None) -> Dict[str, Dict]:
        cmd = ["docker", "buildx", "bake", "--print"]
        for bake_file in self.bake_files:
            cmd.extend(["-f", bake_file])
        if target is not None:
            for t in target:
                cmd.extend(t)
        run_env = os.environ.copy()
        if "GIT_SHA" not in run_env or not run_env.get("GIT_SHA"):
            run_env["GIT_SHA"] = self.get_commit_sha()
        p = subprocess.run(cmd, capture_output=True, env=run_env)
        if p.returncode != 0:
            raise BakeryPlanError(f"Failed to get bake plan: {p.stderr}")
        return json.loads(p.stdout.decode("utf-8"))

    def build(self, target: List[str] = None, load: bool = False, push: bool = False, build_options: List[str] = None):
        cmd = ["docker", "buildx", "bake"]
        for bake_file in self.bake_files:
            cmd.extend(["-f", bake_file])
        if load is True:
            cmd.append("--load")
        if push is True:
            cmd.append("--push")
        if build_options is not None:
            for opt in build_options:
                cmd.append(opt)
        if target is not None:
            for t in target:
                cmd.extend(t)
        run_env = os.environ.copy()
        if "GIT_SHA" not in run_env or not run_env.get("GIT_SHA"):
            run_env["GIT_SHA"] = self.get_commit_sha()
        p = subprocess.run(cmd, env=run_env)
        return p.returncode

