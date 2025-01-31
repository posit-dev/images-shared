import re
import subprocess
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock, patch

import pytest
import tomlkit

from posit_bakery.models import Image, Images, ImageFilter, Manifest, Project

pytestmark = [
    pytest.mark.unit,
    pytest.mark.project,
]


class TestProjectLoad:
    def test_from_context(self, basic_context, basic_expected_num_variants):
        """Test creating a Project object from the basic suite context path"""
        p = Project.load(basic_context)
        assert p.context == basic_context
        assert len(p.config.registry_urls) == 2
        assert "test-image" in p.manifests
        assert len(p.images["test-image"].variants) == basic_expected_num_variants

    def test_load_config(self, basic_context):
        """Test loading the context config.toml file"""
        c = Project.load_config(basic_context)
        assert c.context == basic_context
        assert len(c.registry_urls) == 2

    @pytest.mark.skip(reason="TODO: Handle overrides not specifying all fields")
    def test_load_context_config_with_override(self, basic_tmpcontext):
        """Test loading the context config.toml file"""
        override_config_str = dedent(
            """
            [[registries]]
            host = "docker.io"
            namespace = "posit-dev"
            """
        )
        with open(basic_tmpcontext / "config.override.toml", "w") as f:
            f.write(override_config_str)

        c = Project.load_context_config(basic_tmpcontext, ignore_override=True)
        assert c.context == basic_tmpcontext
        assert len(c.registry_urls) == 2

        c = Project.load_context_config(basic_tmpcontext)
        assert c.context == basic_tmpcontext
        assert len(c.registry_urls) == 1
        assert "docker.io/posit-dev" in c.registry_urls

    def test_load_manifests(self, basic_config_obj, basic_expected_num_variants):
        """Test loading manifests using a config object"""
        m = Project.load_manifests(basic_config_obj)

        assert len(m) == 1
        assert "test-image" in m
        assert isinstance(m["test-image"], Manifest)

    def test_load_images(self, basic_context, basic_expected_num_variants):
        """Test loading imageses using a config object"""
        p = Project.load(basic_context)
        i = p.images

        assert isinstance(i, Images)
        assert len(i) == 1
        assert isinstance(i["test-image"], Image)
        assert len(i["test-image"].variants) == basic_expected_num_variants


class TestProjectBuild:
    def test_render_bake_plan(self, basic_context, basic_expected_num_variants):
        p = Project.load(basic_context)
        plan = p.render_bake_plan()
        assert len(plan.group) == 4
        assert "default" in plan.group
        assert "test-image" in plan.group
        assert "std" in plan.group
        assert "min" in plan.group
        assert len(plan.group["default"].targets) == basic_expected_num_variants
        assert len(plan.target) == basic_expected_num_variants
        for target_data in plan.target.values():
            assert target_data.context
            assert target_data.dockerfile
            assert (Path(basic_context) / target_data.dockerfile).is_file()
            assert not Path(target_data.dockerfile).is_absolute()
            assert target_data.labels
            assert target_data.tags

    def test_build(self, basic_tmpcontext):
        process_mock = MagicMock(returncode=0)
        subprocess.run = MagicMock(return_value=process_mock)
        p = Project.load(basic_tmpcontext)
        p.build()
        subprocess.run.assert_called_once()
        assert subprocess.run.call_args[0][0] == [
            "docker",
            "buildx",
            "bake",
            "--file",
            str(Path(basic_tmpcontext) / ".docker-bake.json"),
        ]


class TestProjectGoss:
    def test_render_dgoss_commands(self, basic_context):
        p = Project.load(basic_context)
        manifest = p.manifests["test-image"].model

        goss_std = manifest.target["std"].goss
        img_std = p.images.filter(
            ImageFilter(image_name="test-image", image_version="1.0.0", target_type="std"),
        ).variants[0]

        goss_min = manifest.target["min"].goss
        img_min = p.images.filter(
            ImageFilter(image_name="test-image", image_version="1.0.0", target_type="min"),
        ).variants[0]

        with patch("posit_bakery.util.find_bin", side_effect=["dgoss", "goss"]):
            commands = p.render_dgoss_commands()

        assert len(commands) == 2

        # min should be first
        cmd = commands[0]
        assert cmd[0] == img_min.tags[0]

        run_env = cmd[1]
        assert isinstance(run_env, dict)
        assert run_env.get("GOSS_PATH") == "goss"
        assert run_env.get("GOSS_FILES_PATH").endswith("test-image/1.0.0/test")
        assert run_env.get("GOSS_SLEEP") is None

        cmdstr = " ".join(cmd[2])
        pat = re.compile(
            r"dgoss run --mount=type=bind,source=.*/test-image/1.0.0/deps,destination=/tmp/deps "
            f"-e IMAGE_TYPE={img_min.target} {img_min.tags[0]} {goss_min.command}"
        )
        assert re.fullmatch(pat, cmdstr) is not None

        # std should be second
        cmd = commands[1]
        assert cmd[0] == img_std.tags[0]

        # Check environment
        run_env = cmd[1]
        assert isinstance(run_env, dict)
        assert run_env.get("GOSS_PATH") == "goss"
        assert run_env.get("GOSS_FILES_PATH").endswith("test-image/1.0.0/test")
        assert run_env.get("GOSS_SLEEP") == str(goss_std.wait)

        # Check command
        cmdstr = " ".join(cmd[2])
        pat = re.compile(
            r"dgoss run --mount=type=bind,source=.*/test-image/1.0.0/deps,destination=/tmp/deps "
            f"-e IMAGE_TYPE={img_std.target} {img_std.tags[0]} {goss_std.command}"
        )
        assert re.fullmatch(pat, cmdstr) is not None

    def test_dgoss(self, basic_context):
        process_mock = MagicMock(returncode=0)
        subprocess.run = MagicMock(return_value=process_mock)
        p = Project.load(basic_context)
        with patch("posit_bakery.util.find_bin", side_effect=["dgoss", "goss"]):
            commands = p.render_dgoss_commands()
        with patch("posit_bakery.util.find_bin", side_effect=["dgoss", "goss"]):
            p.dgoss()
        assert subprocess.run.call_count == 2
        assert subprocess.run.call_args_list[0].args[0] == commands[0][2]
        assert subprocess.run.call_args_list[1].args[0] == commands[1][2]
