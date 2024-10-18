import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import git
from rich import print

from posit_bakery.parser.config import Config
from posit_bakery.parser.manifest import Manifest


class BakePlan:
    def __init__(self, context: Path, config: Config):
        self.context = context
        self.config = config
        self.manifests = []
        self.group = {"default": {"targets": []}}
        self.target = {}

    @staticmethod
    def readable_image_name(image_name: str):
        return image_name.replace("-", " ").title()

    def get_commit_sha(self):
        sha = ""
        try:
            repo = git.Repo(self.context)
            sha = repo.head.object.hexsha
        except Exception as e:
            print(f"[bright_red bold]ERROR:[/bold] Unable to get git commit for labels: {e}")
        return sha

    def add_manifest(self, manifest: Manifest):
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

    def render(self):
        return {
            "group": self.group,
            "target": self.target,
        }

    def to_json(self, output_file: Path = None):
        if output_file is None:
            output_file = self.context / "docker-bake.json"
        with open(output_file, "w") as f:
            json.dump(self.render(), f, indent=2)

    @classmethod
    def new_plan(
        cls, context: Path, skip_override: bool = False, image_name: str = None, image_version: str = None
    ) -> "BakePlan":
        config = Config.load_config_from_context(context, skip_override)
        manifests = Manifest.load_manifests_from_context(context, image_name, image_version)
        plan = cls(context, config)
        for manifest_name, manifest in manifests.items():
            print(f"[bright_blue]Loading manifest {manifest_name}")
            plan.add_manifest(manifest)
        return plan

    def build(self, load: bool = False, push: bool = False, build_options: List[str] = None):
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
