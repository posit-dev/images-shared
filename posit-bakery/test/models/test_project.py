import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import tomlkit

from posit_bakery.models import project, config, manifest


class TestProject:
    def test_from_context(self, basic_context, basic_expected_num_target_builds):
        """Test creating a Project object from the basic suite context path"""
        p = project.Project.load(basic_context)
        assert p.context == basic_context
        assert len(p.config.registry_urls) == 2
        assert "test-image" in p.manifests
        assert len(p.manifests["test-image"].target_builds) == basic_expected_num_target_builds

    def test_load_context_config(self, basic_context):
        """Test loading the context config.toml file"""
        c = project.Project.load_context_config(basic_context)
        assert c.context == basic_context
        assert len(c.registry_urls) == 2

    def test_load_context_config_with_override(self, basic_tmpcontext):
        """Test loading the context config.toml file"""
        override_config_str = """[[registry]]
host = "docker.io"
namespace = "posit-dev"
"""
        with open(basic_tmpcontext / "config.override.toml", "w") as f:
            f.write(override_config_str)

        c = project.Project.load_context_config(basic_tmpcontext, no_override=True)
        assert c.context == basic_tmpcontext
        assert len(c.registry_urls) == 2

        c = project.Project.load_context_config(basic_tmpcontext)
        assert c.context == basic_tmpcontext
        assert len(c.registry_urls) == 1
        assert "docker.io/posit-dev" in c.registry_urls

    def test_load_config_manifests(self, basic_config_obj, basic_expected_num_target_builds):
        """Test loading manifests using a config object"""
        m = project.Project.load_config_manifests(basic_config_obj)
        assert len(m) == 1
        assert "test-image" in m
        assert isinstance(m["test-image"], project.Manifest)
        assert len(m["test-image"].target_builds) == basic_expected_num_target_builds

    def test_new_image(self, basic_tmpcontext):
        """Test creating a new image"""
        p = project.Project.load(basic_tmpcontext)
        p.new_image("new-image")
        new_image_path = Path(basic_tmpcontext) / "new-image"
        assert new_image_path.is_dir()
        assert (new_image_path / "manifest.toml").is_file()
        assert (new_image_path / "template").is_dir()
        assert (new_image_path / "template" / "Containerfile.jinja2").is_file()
        assert (new_image_path / "template" / "test").is_dir()
        assert (new_image_path / "template" / "test" / "goss.yaml.jinja2").is_file()
        assert (new_image_path / "template" / "deps").is_dir()
        assert (new_image_path / "template" / "deps" / "packages.txt.jinja2").is_file()

    def test_new_image_version(self, basic_tmpcontext):
        """Test creating a new version of an image creates the expected files and updates the manifest"""
        image_dir = basic_tmpcontext / "test-image"
        p = project.Project.load(basic_tmpcontext)
        p.new_image_version("test-image", "1.0.1")
        new_version_dir = image_dir / "1.0.1"

        assert new_version_dir.is_dir()
        assert (new_version_dir / "deps").is_dir()
        assert (new_version_dir / "deps" / "ubuntu2204_packages.txt").is_file()
        assert (new_version_dir / "deps" / "ubuntu2204_optional_packages.txt").is_file()
        assert (new_version_dir / "test").is_dir()
        assert (new_version_dir / "test" / "goss.yaml").is_file()
        assert (new_version_dir / "Containerfile.ubuntu2204.min").is_file()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (new_version_dir / "Containerfile.ubuntu2204.min").read_text()
        assert 'ubuntu2204_optional_packages.txt' not in (new_version_dir / "Containerfile.ubuntu2204.min").read_text()
        assert (new_version_dir / "Containerfile.ubuntu2204.std").is_file()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (new_version_dir / "Containerfile.ubuntu2204.std").read_text()
        assert 'ubuntu2204_optional_packages.txt' in (new_version_dir / "Containerfile.ubuntu2204.std").read_text()

        assert "1.0.1" in p.manifests["test-image"].versions
        assert len(p.manifests["test-image"].target_builds) == 4

        with open(image_dir / "manifest.toml", "rb") as f:
            d = tomlkit.loads(f.read())
        assert "1.0.1" in d["build"]
        assert d["build"]["1.0.1"]["latest"] is True
        assert d["build"]["1.0.1"]["os"] == ["Ubuntu 2204"]

    def test_render_bake_plan(self, basic_context, basic_expected_num_target_builds):
        p = project.Project.load(basic_context)
        plan = p.render_bake_plan()
        assert len(plan["group"]) == 4
        assert "default" in plan["group"]
        assert "test-image" in plan["group"]
        assert "std" in plan["group"]
        assert "min" in plan["group"]
        assert len(plan["group"]["default"]["targets"]) == basic_expected_num_target_builds
        assert len(plan["target"]) == basic_expected_num_target_builds
        for target_data in plan["target"].values():
            assert "context" in target_data
            assert "dockerfile" in target_data
            assert (Path(basic_context) / target_data["dockerfile"]).is_file()
            assert not Path(target_data["dockerfile"]).is_absolute()
            assert "labels" in target_data
            assert "tags" in target_data

    def test_build(self, basic_tmpcontext):
        process_mock = MagicMock(returncode=0)
        project.subprocess.run = MagicMock(return_value=process_mock)
        p = project.Project.load(basic_tmpcontext)
        p.build()
        project.subprocess.run.assert_called_once()
        assert project.subprocess.run.call_args[0][0] == ["docker", "buildx", "bake", "--file", str(Path(basic_tmpcontext) / ".docker-bake.json")]

    def test_render_dgoss_commands(self, basic_context):
        p = project.Project.load(basic_context)

        manifest_std = p.manifests["test-image"].filter_target_builds("1.0.0", "std")[0]
        goss_std = manifest_std.goss
        manifest_min = p.manifests["test-image"].filter_target_builds("1.0.0", "min")[0]
        goss_min = manifest_min.goss

        with patch("posit_bakery.models.project.find_bin", side_effect=["dgoss", "goss"]):
            commands = p.render_dgoss_commands()

        assert len(commands) == 2
        # Ensure tags are different
        assert commands[0][0] == manifest_std.get_tags()[0]
        assert commands[1][0] == manifest_min.get_tags()[0]
        # Ensure run env is there, this is impossible to check for the exact value
        for run_env in [commands[0][1], commands[1][1]]:
            assert isinstance(run_env, dict)
            assert run_env["GOSS_PATH"] == "goss"
            assert run_env["GOSS_FILES_PATH"].endswith("test-image/1.0.0/test")
        assert commands[0][1]["GOSS_SLEEP"] == str(goss_std.wait)
        assert "GOSS_SLEEP" not in commands[1][1]
        # Ensure commands are correct
        cmdstr = " ".join(commands[0][2])
        pat = re.compile(
            r"dgoss run --mount=type=bind,source=.*/test-image/1.0.0/deps,destination=/tmp/deps "
            f"-e IMAGE_TYPE={manifest_std.type} {manifest_std.get_tags()[0]} {goss_std.command}"
        )
        assert re.fullmatch(pat, cmdstr) is not None
        cmdstr = " ".join(commands[1][2])
        pat = re.compile(
            r"dgoss run --mount=type=bind,source=.*/test-image/1.0.0/deps,destination=/tmp/deps "
            f"-e IMAGE_TYPE={manifest_min.type} {manifest_min.get_tags()[0]} {goss_min.command}"
        )
        assert re.fullmatch(pat, cmdstr) is not None

    def test_dgoss(self, basic_context):
        process_mock = MagicMock(returncode=0)
        project.subprocess.run = MagicMock(return_value=process_mock)
        p = project.Project.load(basic_context)
        with patch("posit_bakery.models.project.find_bin", side_effect=["dgoss", "goss"]):
            commands = p.render_dgoss_commands()
        with patch("posit_bakery.models.project.find_bin", side_effect=["dgoss", "goss"]):
            p.dgoss()
        assert project.subprocess.run.call_count == 2
        assert project.subprocess.run.call_args_list[0].args[0] == commands[0][2]
        assert project.subprocess.run.call_args_list[1].args[0] == commands[1][2]
