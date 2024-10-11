import json
from datetime import datetime, timezone

from posit_bakery.bake.parser.config import Config
from posit_bakery.bake.parser.manifest import Manifest


class BakePlan:
    def __init__(self, config: Config):
        self.config = config
        self.group = {
            "default": {
                "targets": []
            }
        }
        self.target = {}

    @staticmethod
    def readable_image_name(image_name: str):
        return image_name.replace("-", " ").title()

    def add_manifest(self, manifest: Manifest):
        target_definition = {
            "context": ".",
        }
        for target_build in manifest.target_builds:
            target_name = target_build.name

            # Add target to groups
            if target_build.type not in self.group["default"]["targets"]:
                self.group["default"]["targets"].append(target_build.type)
            if target_build.type not in self.group:
                self.group[target_build.type] = {
                    "targets": []
                }
            self.group[target_build.type]["targets"].append(target_name)

            # Set target definition attributes
            target_definition["dockerfile"] = target_build.containerfile_path
            target_definition["labels"] = {
                "co.posit.image.name": self.readable_image_name(target_build.image_name),
                "co.posit.image.os": target_build.os,
                "co.posit.image.type": target_build.type,
                "co.posit.image.version": target_build.version,
                "org.opencontainers.image.created": datetime.now(tz=timezone.utc).isoformat(),
                "org.opencontainers.image.title": self.readable_image_name(target_build.image_name),
                "org.opencontainers.image.vendor": self.config.vendor,
                "org.opencontainers.image.maintainer": self.config.maintainer,
            }
            if self.config.authors:
                target_definition["labels"]["org.opencontainers.image.authors"] = ", ".join(self.config.authors)
            if self.config.repository_url:
                target_definition["labels"]["org.opencontainers.image.source"] = self.config.repository_url

            target_definition["tags"] = []
            for registry_url in self.config.get_registry_base_urls():
                target_definition["tags"].extend(target_build.render_fq_tags(registry_url))
            self.target[target_name] = target_definition

    def render(self):
        return {
            "group": self.group,
            "target": self.target,
        }

    def to_json(self, output_file="bake-plan.json"):
        with open(output_file, "w") as f:
            json.dump(self.render(), f, indent=2)
