from pathlib import Path
from typing import List
from unittest.mock import patch

import pytest

from posit_bakery.models import Image, ImageFilter
from posit_bakery.models.project.bake import BakePlan
from posit_bakery.models.config.document import ConfigDocument

from ..fixtures import (
    config_simple,
    config_multi_registry,
    manifest_simple,
    manifest_latest,
    manifest_multi_build,
    manifest_multi_os,
    manifest_matrix,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.bake,
]


@pytest.fixture(autouse=True)
def patch_is_file():
    """Patch pathlib.Path.is_file to always return True

    We use is_file to find the appropriate Containerfile for each ImageVariant
    """
    with patch("pathlib.Path.is_file", return_value=True, autospec=True) as p:
        yield p


@pytest.fixture(autouse=True)
def patch_is_dir():
    """Patch pathlib.Path.is_dir to always return True

    We use is_dir to find the test and dependency directories for goss
    """
    with patch("pathlib.Path.is_dir", return_value=True, autospec=True) as p:
        yield p


class TestBakePlan:
    @staticmethod
    def complete_metadata(images: List[Image], config: ConfigDocument):
        for image in images:
            for variant in image.variants:
                variant.complete_metadata(config)
        return images

    def test_bake_plan_simple(self, config_simple, manifest_simple):
        """Test that simple bake plan contains ALL the expected fields"""
        expected_uid = "simple-image-0-1-0-ubuntu2404-min"

        images: List[Image] = [Image.load(Path("simple-image"), manifest_simple)]
        images = self.complete_metadata(images, config_simple)

        plan: BakePlan = BakePlan.create(images=images)

        assert len(plan.group) == 3
        assert expected_uid in plan.group["default"].targets
        assert expected_uid in plan.group["simple-image"].targets
        assert expected_uid in plan.group["min"].targets

        assert len(plan.target) == 1
        assert expected_uid in plan.target

        labels = plan.target[expected_uid].labels
        assert labels["co.posit.image.name"] == "simple-image"
        assert labels["co.posit.image.version"] == "0.1.0"
        assert labels["co.posit.image.os"] == "Ubuntu 24.04"
        assert labels["co.posit.image.type"] == "min"

        assert "org.opencontainers.image.created" in labels
        assert labels["org.opencontainers.image.title"] == "simple-image"
        assert labels["org.opencontainers.image.vendor"] == "Posit Software, PBC"
        assert labels["org.opencontainers.image.authors"] == "author1@sub.tld, Author Name <author.name@example.com>"
        assert labels["org.opencontainers.image.maintainer"] == "author.name@posit.co"
        assert labels["org.opencontainers.image.source"] == "github.com/posit-dev/images-fakename"

        tags = plan.target[expected_uid].tags
        assert "docker.io/posit/simple-image:0.1.0-ubuntu-24.04-min" in tags
        # Latest tags should not apply to minimal image
        assert "docker.io/posit/simple-image:latest" not in tags

    def test_bake_plan_tags_latest(self, config_simple, manifest_latest):
        """Test that bake plan for the latest images sets the latest tags

        We only check tags here since test_bake_plan_simple checks other fields
        """
        images: List[Image] = [Image.load(Path("latest-image"), manifest_latest)]
        images = self.complete_metadata(images, config_simple)

        plan: BakePlan = BakePlan.create(images=images)

        # Standard Image
        tags_std = plan.target["latest-image-1-2-3-ubuntu2404-std"].tags
        assert "docker.io/posit/latest-image:1.2.3-ubuntu-24.04-std" in tags_std
        assert "docker.io/posit/latest-image:1.2.3-std" in tags_std
        assert "docker.io/posit/latest-image:1.2.3" in tags_std
        assert "docker.io/posit/latest-image:ubuntu-24.04-std" in tags_std
        assert "docker.io/posit/latest-image:ubuntu-24.04" in tags_std
        assert "docker.io/posit/latest-image:std" in tags_std
        assert "docker.io/posit/latest-image:latest" in tags_std

        # Minimal Image
        tags_min = plan.target["latest-image-1-2-3-ubuntu2404-min"].tags
        assert "docker.io/posit/latest-image:1.2.3-ubuntu-24.04-min" in tags_min
        assert "docker.io/posit/latest-image:1.2.3-min" in tags_min
        assert "docker.io/posit/latest-image:ubuntu-24.04-min" in tags_min
        assert "docker.io/posit/latest-image:min" in tags_min
        # Latest tags should not apply to minimal image
        assert "docker.io/posit/latest-image:latest" not in tags_min

    def test_bake_plan_multi_build(self, config_simple, manifest_multi_build):
        """Test bake plan with multiple builds and default targets"""
        expected_uid_1 = "multi-build-image-0-1-0-ubuntu2404-min"
        expected_uid_2 = "multi-build-image-0-1-0-ubuntu2404-std"
        expected_uid_3 = "multi-build-image-1-2-3-ubuntu2404-min"
        expected_uid_4 = "multi-build-image-1-2-3-ubuntu2404-std"

        images: List[Image] = [Image.load(Path("multi-build-image"), manifest_multi_build)]
        images = self.complete_metadata(images, config_simple)

        plan: BakePlan = BakePlan.create(images=images)

        # Check that we
        assert len(plan.group) == 4
        assert expected_uid_1 in plan.group["default"].targets
        assert expected_uid_2 in plan.group["default"].targets
        assert expected_uid_3 in plan.group["default"].targets
        assert expected_uid_4 in plan.group["default"].targets

        assert expected_uid_1 in plan.group["multi-build-image"].targets
        assert expected_uid_2 in plan.group["multi-build-image"].targets
        assert expected_uid_3 in plan.group["multi-build-image"].targets
        assert expected_uid_4 in plan.group["multi-build-image"].targets

        assert expected_uid_1 in plan.group["min"].targets
        assert expected_uid_3 in plan.group["min"].targets

        assert expected_uid_2 in plan.group["std"].targets
        assert expected_uid_4 in plan.group["std"].targets

        assert len(plan.target) == 4
        assert expected_uid_1 in plan.target
        assert expected_uid_2 in plan.target
        assert expected_uid_3 in plan.target
        assert expected_uid_4 in plan.target

    def test_bake_plan_multi_os(self, config_simple, manifest_multi_os):
        """Test bake plan with multiple OS and default targets"""
        expected_uid_1 = "multi-os-image-2-1-5-ubuntu2404-min"
        expected_uid_2 = "multi-os-image-2-1-5-ubuntu2404-std"
        expected_uid_3 = "multi-os-image-2-1-5-ubuntu2204-min"
        expected_uid_4 = "multi-os-image-2-1-5-rockylinux9-std"
        expected_uid_5 = "multi-os-image-2-1-5-rockylinux9-min"
        expected_uid_6 = "multi-os-image-2-1-5-rockylinux9-std"

        images: List[Image] = [Image.load(Path("multi-os-image"), manifest_multi_os)]
        images = self.complete_metadata(images, config_simple)

        plan: BakePlan = BakePlan.create(images=images)

        assert len(plan.group) == 4

        assert expected_uid_1 in plan.group["default"].targets
        assert expected_uid_2 in plan.group["default"].targets
        assert expected_uid_3 in plan.group["default"].targets
        assert expected_uid_4 in plan.group["default"].targets
        assert expected_uid_5 in plan.group["default"].targets
        assert expected_uid_6 in plan.group["default"].targets

        assert expected_uid_1 in plan.group["multi-os-image"].targets
        assert expected_uid_2 in plan.group["multi-os-image"].targets
        assert expected_uid_3 in plan.group["multi-os-image"].targets
        assert expected_uid_4 in plan.group["multi-os-image"].targets
        assert expected_uid_5 in plan.group["multi-os-image"].targets
        assert expected_uid_6 in plan.group["multi-os-image"].targets

        assert expected_uid_1 in plan.group["min"].targets
        assert expected_uid_3 in plan.group["min"].targets
        assert expected_uid_5 in plan.group["min"].targets

        assert expected_uid_2 in plan.group["std"].targets
        assert expected_uid_4 in plan.group["std"].targets
        assert expected_uid_6 in plan.group["std"].targets

        assert len(plan.target) == 6
        assert expected_uid_1 in plan.target
        assert expected_uid_2 in plan.target
        assert expected_uid_3 in plan.target
        assert expected_uid_4 in plan.target
        assert expected_uid_5 in plan.target
        assert expected_uid_6 in plan.target

    def test_bake_plan_matrix(self, config_simple, manifest_matrix):
        """Test large matrix of builds and targets"""
        images: List[Image] = [Image.load(Path("matrix-image"), manifest_matrix)]
        images = self.complete_metadata(images, config_simple)

        plan: BakePlan = BakePlan.create(images=images)

        assert len(plan.group) == 6
        assert len(plan.group["default"].targets) == 20
        assert len(plan.group["matrix-image"].targets) == 20
        assert len(plan.group["std"].targets) == 5
        assert len(plan.group["min"].targets) == 5
        assert len(plan.group["complex"].targets) == 5
        assert len(plan.group["preview"].targets) == 5

        assert len(plan.target) == 20

    def test_bake_plan_multi_registry(self, config_multi_registry, manifest_simple):
        """Test bake plan with multiple registries"""
        images: List[Image] = [Image.load(Path("simple-image"), manifest_simple)]
        images = self.complete_metadata(images, config_multi_registry)

        plan: BakePlan = BakePlan.create(images=images)

        assert len(plan.group) == 3
        assert len(plan.target) == 1

        # Ensure both image registries are included in the tags
        tags = plan.target["simple-image-0-1-0-ubuntu2404-min"].tags
        assert "docker.io/posit/simple-image:0.1.0-ubuntu-24.04-min" in tags
        assert "ghcr.io/posit-dev/simple-image:0.1.0-ubuntu-24.04-min" in tags

    def test_bake_plan_filter(
        self,
        basic_images_obj,
        basic_manifest_os_plus_versions,
        basic_expected_num_variants,
    ):
        """Test bake plan filtering"""
        plan: BakePlan

        images = basic_images_obj.filter(ImageFilter(build_version="1.0.0")).values()
        plan = BakePlan.create(images=images)
        assert len(plan.target) == basic_expected_num_variants

        images = basic_images_obj.filter(ImageFilter(target_type="min")).values()
        plan = BakePlan.create(images=images)
        assert len(plan.target) == len(basic_manifest_os_plus_versions)

        images = basic_images_obj.filter(ImageFilter(target_type="std")).values()
        plan = BakePlan.create(images=images)
        assert len(plan.target) == len(basic_manifest_os_plus_versions)
