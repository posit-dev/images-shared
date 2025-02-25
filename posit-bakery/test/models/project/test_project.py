import re
import subprocess
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock, patch, PropertyMock

import jinja2
import pytest
import tomlkit

from posit_bakery.error import BakeryFileError, BakeryImageNotFoundError, BakeryToolNotFoundError, BakeryToolError
from posit_bakery.models import Image, Images, ImageFilter, Manifest, Project, Config
from posit_bakery.models.image import ImageMetadata
from posit_bakery.models.image.variant import ImageVariant
from posit_bakery.models.manifest.snyk import SnykContainerSubcommand
from posit_bakery.models.project.bake import target_uid
from posit_bakery.templating import TPL_CONFIG_TOML
from test.models import helpers

pytestmark = [
    pytest.mark.unit,
    pytest.mark.project,
]


class TestProjectCreate:
    def test_create(self, tmpdir):
        """Test creating a Project object from a context path"""
        p = Project.create(tmpdir)
        assert Path(tmpdir).absolute() == p.context.absolute()
        assert (Path(tmpdir) / "config.toml").absolute() == p.config.filepath.absolute()
        assert (Path(tmpdir) / "config.toml").is_file()
        contents = (Path(tmpdir) / "config.toml").read_text()
        expected_contents = jinja2.Environment().from_string(TPL_CONFIG_TOML).render(repo_url="<REPLACE ME>")
        assert tomlkit.loads(contents) == tomlkit.loads(expected_contents)

    def test_create_context_is_file(self, tmpdir):
        """Test creating a Project object from a context path that is a file"""
        with open(tmpdir / "file.txt", "w") as f:
            f.write("test")
        with pytest.raises(BakeryFileError):
            Project.create(tmpdir / "file.txt")

    def test_create_project_directory_is_created(self, tmpdir):
        assert not (Path(tmpdir) / "new_project").exists()
        Project.create(tmpdir / "new_project")
        assert (Path(tmpdir) / "new_project").exists()
        assert (Path(tmpdir) / "new_project" / "config.toml").exists()

    def test_create_project_exists(self, basic_context):
        """Test creating a Project object from a context path"""
        with pytest.raises(BakeryFileError):
            Project.create(basic_context)


class TestProjectExists:
    def test_exists(self, basic_context):
        """Test checking if a project exists"""
        assert Project.exists(basic_context)

    def test_not_exists(self, tmpdir):
        """Test checking if a project does not exist"""
        assert not Project.exists(tmpdir)

    def test_directory_does_not_exist(self, tmpdir):
        """Test checking if a project does not exist"""
        assert not Project.exists(tmpdir / "test_directory")

    def test_context_is_file(self, tmpdir):
        """Test checking if a project does not exist"""
        with open(tmpdir / "file.txt", "w") as f:
            f.write("test")
        with pytest.raises(BakeryFileError):
            Project.exists(tmpdir / "file.txt")


class TestProjectHasImages:
    def test_has_images(self, basic_context):
        """Test returns true if a project has images"""
        project = Project.load(basic_context)
        assert project.has_images()

    def test_has_images_false(self, tmpdir):
        """Test returns false when no images are present"""
        project = Project.create(tmpdir)
        assert not project.has_images()


class TestProjectLoad:
    def test_from_context(self, basic_context, basic_expected_num_variants):
        """Test creating a Project object from the basic suite context path"""
        p = Project.load(basic_context)
        assert p.context == basic_context
        assert len(p.config.registry_urls) == 2
        assert "test-image" in p.manifests
        assert len(p.images["test-image"].variants) == basic_expected_num_variants

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

    def test_load_context_does_not_exist(self, tmpdir):
        """Test loading a project from a context that does not exist"""
        with pytest.raises(BakeryFileError, match="Project context does not exist."):
            Project.load(Path(tmpdir) / "test_directory")

    def test_load_context_is_file(self, tmpdir):
        """Test loading a project from a context that is a file"""
        with open(tmpdir / "file.txt", "w") as f:
            f.write("test")
        with pytest.raises(BakeryFileError, match="Project context is not a directory."):
            Project.load(tmpdir / "file.txt")

    def test_load_config_does_not_exist(self, tmpdir):
        """Test loading a project from a context that does not exist"""
        with pytest.raises(BakeryFileError, match="Project config.toml file not found."):
            Project.load(tmpdir)


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

    def test_render_bake_plan_no_images(self, tmpdir):
        p = Project.create(tmpdir)
        with pytest.raises(BakeryImageNotFoundError, match="No images found in the project."):
            p.render_bake_plan()

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

    def test_build_no_images(self, tmpdir):
        p = Project.create(tmpdir)
        with pytest.raises(BakeryImageNotFoundError, match="No images found in the project."):
            p.build()


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
        assert cmd[0].tags[0] == img_min.tags[0]

        run_env = cmd[1]
        assert isinstance(run_env, dict)
        assert run_env.get("GOSS_PATH") == "goss"
        assert run_env.get("GOSS_FILES_PATH").endswith("test-image/1.0.0/test")
        assert "--format json" in run_env.get("GOSS_OPTS")
        assert "--no-color" in run_env.get("GOSS_OPTS")
        assert run_env.get("GOSS_SLEEP") is None

        cmdstr = " ".join(cmd[2])
        pat = re.compile(
            r"dgoss run --mount=type=bind,source=.*/test-image/1.0.0/deps,destination=/tmp/deps "
            f"-e IMAGE_TYPE={img_min.target} {img_min.tags[0]} {goss_min.command}"
        )
        assert re.fullmatch(pat, cmdstr) is not None

        # std should be second
        cmd = commands[1]
        assert cmd[0] == img_std

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

    def test_dgoss(self, basic_tmpcontext):
        process_mock = MagicMock(returncode=0)
        type(process_mock).stdout = PropertyMock(side_effect=[b"{}", b"{}"])
        subprocess.run = MagicMock(return_value=process_mock)
        p = Project.load(basic_tmpcontext)
        with patch("posit_bakery.util.find_bin", side_effect=["dgoss", "goss"]):
            commands = p.render_dgoss_commands()
        with patch("posit_bakery.util.find_bin", side_effect=["dgoss", "goss"]):
            p.dgoss()
        assert subprocess.run.call_count == 2
        assert subprocess.run.call_args_list[0].args[0] == commands[0][2]
        assert subprocess.run.call_args_list[1].args[0] == commands[1][2]

    def test_dgoss_no_images(self, tmpdir):
        p = Project.create(tmpdir)
        with pytest.raises(BakeryImageNotFoundError, match="No images found in the project."):
            p.dgoss()


@pytest.mark.snyk
class TestProjectSnyk:
    @pytest.mark.parametrize("snyk_config,expected_args", helpers.snyk_test_argument_testcases())
    def test__get_snyk_container_test_arguments(self, basic_tmpcontext, snyk_config, expected_args):
        project = Project.load(basic_tmpcontext)
        metadata = ImageMetadata(
            name="test-image",
            version="1.0.0",
            context=basic_tmpcontext,
            snyk=snyk_config,
        )
        variant = ImageVariant(
            meta=metadata,
            latest=False,
            os="Ubuntu 22.04",
            target="std",
            containerfile=basic_tmpcontext / metadata.name / metadata.version / "Containerfile.ubuntu2204.std",
        )
        expected_args = helpers.try_format_values(
            expected_args,
            variant=variant,
            context=basic_tmpcontext,
            uid=target_uid(variant.meta.name, variant.meta.version, variant),
        )
        result = project._get_snyk_container_test_arguments(variant)
        assert result == expected_args
        if variant.meta.snyk.test.output.json_file or variant.meta.snyk.test.output.sarif_file:
            assert (basic_tmpcontext / "results" / "snyk" / "test").exists()

    @pytest.mark.parametrize("snyk_config,expected_args", helpers.snyk_monitor_argument_testcases())
    def test__get_snyk_container_monitor_arguments(self, basic_context, snyk_config, expected_args):
        mock_meta = MagicMock(spec=ImageMetadata, snyk=snyk_config, name="test-image", context=basic_context)
        mock_variant = MagicMock(spec=ImageVariant, meta=mock_meta)
        result = Project._get_snyk_container_monitor_arguments(mock_variant)
        assert result == expected_args

    @pytest.mark.parametrize("snyk_config,expected_args", helpers.snyk_sbom_argument_testcases())
    def test__get_snyk_container_sbom_arguments(self, basic_context, snyk_config, expected_args):
        mock_meta = MagicMock(spec=ImageMetadata, snyk=snyk_config, name="test-image", context=basic_context)
        mock_variant = MagicMock(spec=ImageVariant, meta=mock_meta)
        result = Project._get_snyk_container_sbom_arguments(mock_variant)
        assert result == expected_args

    @pytest.mark.parametrize("snyk_subcommand,snyk_config,expected_args", helpers.snyk_all_argument_testcases())
    def test_render_snyk_commands(self, basic_tmpcontext, snyk_subcommand, snyk_config, expected_args):
        p = Project.load(basic_tmpcontext)
        for name, image in p.images.items():
            for variant in image.variants:
                variant.meta.snyk = snyk_config
        with patch.dict("os.environ", clear=True):
            with patch("posit_bakery.util.find_bin", return_value="snyk"):
                result = p.render_snyk_commands(subcommand=snyk_subcommand)
        assert len(result) == len(p.images.variants)
        for variant in p.images.variants:
            variant_expected_args = helpers.try_format_values(
                expected_args,
                variant=variant,
                context=basic_tmpcontext,
                uid=target_uid(variant.meta.name, variant.meta.version, variant),
            )
            variant_expected_args.append(variant.tags[0])
            command_set = [c for c in result if c[0] == variant.tags[0]]
            assert len(command_set) == 1
            command_set = command_set[0]
            assert len(command_set) == 3
            assert variant_expected_args == command_set[2]

    @pytest.mark.parametrize("snyk_subcommand", [e for e in SnykContainerSubcommand])
    def test_snyk_success(self, caplog, basic_tmpcontext, snyk_subcommand):
        p = Project.load(basic_tmpcontext)
        process_mock = MagicMock(returncode=0)
        type(process_mock).stdout = PropertyMock(side_effect=[b"00000000-0000-0000-0000-000000000000", b"{}", b"{}"])
        subprocess.run = MagicMock(return_value=process_mock)
        with patch.dict("os.environ", clear=True):
            with patch("posit_bakery.util.find_bin", return_value="snyk"):
                p.snyk(subcommand=snyk_subcommand)
        assert subprocess.run.call_count == len(p.images.variants) + 1
        assert subprocess.run.call_args_list[0].args[0] == ["snyk", "config", "get", "org"]
        for i, command in enumerate(subprocess.run.call_args_list[1:]):
            assert command.args[0][0:3] == ["snyk", "container", snyk_subcommand]
        assert "ERROR" not in caplog.text
        assert "WARNING" not in caplog.text

    @patch("posit_bakery.util.find_bin", side_effect=BakeryToolNotFoundError)
    def test_snyk_no_bin(self, mock_find_bin, basic_context):
        p = Project.load(basic_context)
        with pytest.raises(BakeryToolNotFoundError):
            p.snyk(subcommand=SnykContainerSubcommand.test)

    @patch("posit_bakery.util.find_bin", return_value="snyk")
    def test_snyk_invalid_subcommand(self, mock_find_bin, basic_context):
        p = Project.load(basic_context)
        with pytest.raises(BakeryToolError, match="snyk subcommand must be"):
            p.snyk(subcommand="invalid")

    @patch("posit_bakery.util.find_bin", return_value="snyk")
    def test_snyk_no_org_warning(self, mock_find_bin, caplog, basic_tmpcontext):
        p = Project.load(basic_tmpcontext)
        process_mock = MagicMock(returncode=0, stdout=b"")
        subprocess.run = MagicMock(return_value=process_mock)
        with patch.dict("os.environ", clear=True):
            p.snyk(subcommand=SnykContainerSubcommand.test)
        assert subprocess.run.call_count == len(p.images.variants) + 1
        assert subprocess.run.call_args_list[0].args[0] == ["snyk", "config", "get", "org"]
        for i, command in enumerate(subprocess.run.call_args_list[1:]):
            assert command.args[0][0:3] == ["snyk", "container", "test"]
        assert "WARNING" in caplog.text

    @patch("posit_bakery.util.find_bin", return_value="snyk")
    def test_snyk_org_environ_no_warning(self, mock_find_bin, caplog, basic_tmpcontext):
        p = Project.load(basic_tmpcontext)
        process_mock = MagicMock(returncode=0, stdout=b"")
        subprocess.run = MagicMock(return_value=process_mock)
        with patch.dict("os.environ", {"SNYK_ORG": "test"}):
            p.snyk(subcommand=SnykContainerSubcommand.test)
        assert subprocess.run.call_count == len(p.images.variants) + 1
        assert subprocess.run.call_args_list[0].args[0] == ["snyk", "config", "get", "org"]
        for i, command in enumerate(subprocess.run.call_args_list[1:]):
            assert command.args[0][0:3] == ["snyk", "container", "test"]
        assert "WARNING" not in caplog.text
