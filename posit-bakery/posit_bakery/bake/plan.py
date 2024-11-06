import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Union, Dict, Any

import git
from rich import print

from posit_bakery.parser.config import Config
from posit_bakery.parser.manifest import Manifest


class BakePlan:
    def __init__(self, context: Union[str, bytes, os.PathLike], config: Config) -> None:
        # Context is the root directory of the project where config.toml exists
        self.context: Path = Path(context)

        # The project Config for the images being built
        self.config: Config = config

        # List of Manifests being built
        self.manifests: List[Manifest] = []

        # Docker Buildx Bake File Reference: https://docs.docker.com/build/bake/reference/

        # Group section of the bake plan
        # Always in the format of {"group_name": {"targets": ["target_names"...]}}
        self.group: Dict[str, Dict[str, List]] = {"default": {"targets": []}}
        # Target section of the bake plan
        # Always in the format of
        # {"target_name": {"context": ".", "dockerfile": "<PATH>", "labels": {"key": "value"...}, "tags": ["<TAG>"...]}}
        self.target: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def readable_image_name(image_name: str) -> str:
        """Gives a best attempt at a human-readable image name"""
        return image_name.replace("-", " ").title()

    def get_commit_sha(self) -> str:
        """Get the git commit SHA for the current context"""
        sha = ""
        try:
            repo = git.Repo(self.context)
            sha = repo.head.object.hexsha
        except Exception as e:
            print(f"[bright_red bold]ERROR:[/bold] Unable to get git commit for labels: {e}")
        return sha

    def add_manifest(self, manifest: Manifest) -> None:
        """Adds a manifest to the list of manifests to be built and renders appropriate bake plan for each target build

        :param manifest: The manifest to be added
        """
        for target_build in manifest.target_builds:
            target_definition = {
                "context": ".",
            }
            target_name = target_build.name

            # Add target to groups
            if target_build.type not in self.group["default"]["targets"]:
                self.group["default"]["targets"].append(target_build.type)
            if target_build.type not in self.group:
                self.group[target_build.type] = {"targets": []}
            if manifest.name not in self.group:
                self.group[manifest.name] = {"targets": []}
            self.group[target_build.type]["targets"].append(target_name)
            self.group[manifest.name]["targets"].append(target_name)

            # Set target definition attributes
            target_definition["dockerfile"] = str(target_build.containerfile_path)
            target_definition["labels"] = {
                "co.posit.image.name": self.readable_image_name(target_build.image_name),
                "co.posit.image.os": target_build.os,
                "co.posit.image.type": target_build.type,
                "co.posit.image.version": target_build.version,
                "org.opencontainers.image.created": datetime.now(tz=timezone.utc).isoformat(),
                "org.opencontainers.image.title": self.readable_image_name(target_build.image_name),
                "org.opencontainers.image.vendor": self.config.vendor,
                "org.opencontainers.image.maintainer": self.config.maintainer,
                "org.opencontainers.image.revision": self.get_commit_sha(),
            }
            if self.config.authors:
                target_definition["labels"]["org.opencontainers.image.authors"] = ", ".join(self.config.authors)
            if self.config.repository_url:
                target_definition["labels"]["org.opencontainers.image.source"] = self.config.repository_url

            target_definition["tags"] = []
            for registry_url in self.config.get_registry_base_urls():
                target_definition["tags"].extend(target_build.render_fq_tags(registry_url))
            self.target[target_name] = target_definition
        self.manifests.append(manifest)

    def render(self) -> Dict[str, Dict[str, Any]]:
        """Renders the bake plan as a dictionary"""
        return {
            "group": self.group,
            "target": self.target,
        }

    def to_json(self, output_file: Union[str, bytes, os.PathLike] = None) -> None:
        """Writes the bake plan to a JSON file

        :param output_file: The output file to write the bake plan to
        """
        if output_file is None:
            output_file = self.context / "docker-bake.json"
        with open(output_file, "w") as f:
            json.dump(self.render(), f, indent=2)

    @classmethod
    def new_plan(
            cls,
            context: Union[str, bytes, os.PathLike],
            skip_override: bool = False,
            image_name: str = None,
            image_version: str = None,
    ) -> "BakePlan":
        """Creates a new BakePlan from a context directory

        :param context: The context directory
        :param skip_override: Skip loading the override config file
        :param image_name: Filter the plan generation by image name
        :param image_version: Filter the plan generation by image version
        """
        config = Config.load_config_from_context(context, skip_override)
        manifests = Manifest.load_manifests_from_context(context, image_name, image_version)
        plan = cls(context, config)
        for manifest_name, manifest in manifests.items():
            print(f"[bright_blue]Loading manifest {manifest_name}")
            plan.add_manifest(manifest)
        return plan

    def build(self, load: bool = False, push: bool = False, build_options: List[str] = None):
        """Builds the images defined in the bake plan

        :param load: Load the built images into the local Docker daemon
        :param push: Push the built images to the registry
        :param build_options: Additional build options to pass to `docker buildx bake`
        """
        bake_file = self.context / ".docker-bake.json"
        self.to_json(bake_file)
        cmd = ["docker", "buildx", "bake", "--file", str(bake_file)]
        if load:
            cmd.append("--load")
        if push:
            cmd.append("--push")
        if build_options:
            cmd.extend(build_options)
        run_env = os.environ.copy()
        p = subprocess.run(cmd, env=run_env, cwd=self.context)
        bake_file.unlink()
        return p.returncode
