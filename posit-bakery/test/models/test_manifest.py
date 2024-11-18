from pathlib import Path
from unittest.mock import MagicMock

import pytest
import tomlkit

from posit_bakery.error import BakeryFileNotFoundError
from posit_bakery.models import manifest, config


class TestGossConfig:
    def test_goss_config(self, basic_manifest_obj):
        """Test creating a basic GossConfig object does not raise an exception"""
        target_data = basic_manifest_obj.document["target"]["min"].unwrap()
        target_data["type"] = "min"
        build_data = basic_manifest_obj.document["build"]["1.0.0"].unwrap()
        build_data["version"] = "1.0.0"
        version_context = basic_manifest_obj.context / "1.0.0"
        manifest.GossConfig(
            version_context=version_context,
            target_data=target_data,
            build_data=build_data,
            const={"image_name": "test-image"},
        )

    def test_default_deps(self, basic_manifest_obj):
        """Test the default deps path generation for a GossConfig object"""
        target_data = basic_manifest_obj.document["target"]["min"].unwrap()
        target_data["type"] = "min"
        build_data = basic_manifest_obj.document["build"]["1.0.0"].unwrap()
        build_data["version"] = "1.0.0"
        version_context = basic_manifest_obj.context / "1.0.0"
        goss_config = manifest.GossConfig(
            version_context=version_context,
            target_data=target_data,
            build_data=build_data,
            const={"image_name": "test-image"},
        )
        assert goss_config.deps == version_context / "deps"

    def test_default_test_path(self, basic_manifest_obj):
        """Test the default test path generation for a GossConfig object"""
        target_data = basic_manifest_obj.document["target"]["min"].unwrap()
        target_data["type"] = "min"
        build_data = basic_manifest_obj.document["build"]["1.0.0"].unwrap()
        build_data["version"] = "1.0.0"
        version_context = basic_manifest_obj.context / "1.0.0"
        goss_config = manifest.GossConfig(
            version_context=version_context,
            target_data=target_data,
            build_data=build_data,
            const={"image_name": "test-image"},
        )
        assert goss_config.test_path == version_context / "test"

    def test_deps_render(self, basic_context, basic_manifest_obj):
        """Test the deps path generation with template rendering for a GossConfig object"""
        target_data = basic_manifest_obj.document["target"]["min"].unwrap()
        target_data["type"] = "min"
        build_data = basic_manifest_obj.document["build"]["1.0.0"].unwrap()
        build_data["version"] = "1.0.0"
        version_context = basic_manifest_obj.context / "1.0.0"
        goss_config = manifest.GossConfig(
            version_context=version_context,
            target_data=target_data,
            build_data=build_data,
            const={"image_name": "test-image"},
            deps=basic_context / "{{ image_name }}" / "deps" / "{{ build.version }}",
        )
        assert goss_config.deps == basic_context / "test-image" / "deps" / "1.0.0"

    def test_test_path_render(self, basic_context, basic_manifest_obj):
        """Test the test path generation with template rendering for a GossConfig object"""
        target_data = basic_manifest_obj.document["target"]["min"].unwrap()
        target_data["type"] = "min"
        build_data = basic_manifest_obj.document["build"]["1.0.0"].unwrap()
        build_data["version"] = "1.0.0"
        version_context = basic_manifest_obj.context / "1.0.0"
        goss_config = manifest.GossConfig(
            version_context=version_context,
            target_data=target_data,
            build_data=build_data,
            const={"image_name": "test-image"},
            test_path=basic_context / "{{ image_name }}" / "test" / "{{ target.type }}",
        )
        assert goss_config.test_path == basic_context / "test-image" / "test" / "min"

    def test_wait_render(self, basic_manifest_obj):
        """Test the wait value with template rendering for a GossConfig object"""
        target_data = basic_manifest_obj.document["target"]["min"].unwrap()
        target_data["type"] = "min"
        build_data = basic_manifest_obj.document["build"]["1.0.0"].unwrap()
        build_data["version"] = "1.0.0"
        version_context = basic_manifest_obj.context / "1.0.0"
        goss_config = manifest.GossConfig(
            version_context=version_context,
            target_data=target_data,
            build_data=build_data,
            const={"image_name": "test-image", "goss_wait": 10},
            wait="{{ goss_wait }}",
        )
        assert goss_config.wait == 10

    def test_command_render(self, basic_manifest_obj):
        """Test the command value with template rendering for a GossConfig object"""
        target_data = basic_manifest_obj.document["target"]["min"].unwrap()
        target_data["type"] = "min"
        build_data = basic_manifest_obj.document["build"]["1.0.0"].unwrap()
        build_data["version"] = "1.0.0"
        version_context = basic_manifest_obj.context / "1.0.0"
        goss_config = manifest.GossConfig(
            version_context=version_context,
            target_data=target_data,
            build_data=build_data,
            const={"image_name": "test-image", "goss_command": "start_app"},
            command="{{ goss_command }}",
        )
        assert goss_config.command == "start_app"


class TestTargetBuild:
    @pytest.fixture
    def target_data_min(self, basic_manifest_obj):
        d = basic_manifest_obj.document["target"]["min"].unwrap()
        d["type"] = "min"
        return d

    @pytest.fixture
    def target_data_std(self, basic_manifest_obj):
        d = basic_manifest_obj.document["target"]["std"].unwrap()
        d["type"] = "std"
        return d

    @pytest.fixture
    def build_data(self, basic_manifest_obj):
        d = basic_manifest_obj.document["build"]["1.0.0"].unwrap()
        d["version"] = "1.0.0"
        d["os"] = d["os"][0]
        return d

    def test_target_build(self, basic_manifest_obj, target_data_min, build_data):
        """Test creating a basic TargetBuild object does not raise an exception"""
        manifest.TargetBuild(
            manifest_context=basic_manifest_obj.context,
            config=basic_manifest_obj.config,
            target_data=target_data_min,
            build_data=build_data,
            image_name=basic_manifest_obj.image_name,
            **build_data,
            **target_data_min,
        )

    def test_default_const(self, basic_manifest_obj, target_data_min, build_data):
        """Test the default const values for a TargetBuild object"""
        target_build = manifest.TargetBuild(
            manifest_context=basic_manifest_obj.context,
            config=basic_manifest_obj.config,
            target_data=target_data_min,
            build_data=build_data,
            image_name=basic_manifest_obj.image_name,
            **build_data,
            **target_data_min,
        )
        assert target_build.const == {"image_name": "test-image"}

    def test_containerfile_default_resolution(self, basic_manifest_obj, target_data_min, target_data_std, build_data):
        """Test that the default containerfile is resolved correctly in the basic test suite"""
        target_build = manifest.TargetBuild(
            manifest_context=basic_manifest_obj.context,
            config=basic_manifest_obj.config,
            target_data=target_data_min,
            build_data=build_data,
            image_name=basic_manifest_obj.image_name,
            **build_data,
            **target_data_min,
        )
        assert target_build.containerfile == "Containerfile.ubuntu2204.min"
        assert target_build.containerfile_path == basic_manifest_obj.context / "1.0.0" / "Containerfile.ubuntu2204.min"

        target_build = manifest.TargetBuild(
            manifest_context=basic_manifest_obj.context,
            config=basic_manifest_obj.config,
            target_data=target_data_std,
            build_data=build_data,
            image_name=basic_manifest_obj.image_name,
            **build_data,
            **target_data_std,
        )
        assert target_build.containerfile == "Containerfile.ubuntu2204.std"
        assert target_build.containerfile_path == basic_manifest_obj.context / "1.0.0" / "Containerfile.ubuntu2204.std"

    def test_containerfile_multipattern_resolution(self, tmpdir):
        """More aggressive tests around containerfile resolution when multiple patterns are present"""
        image_context = Path(tmpdir) / "test-image"
        versioned_context = image_context / "1.0.0"
        versioned_context.mkdir(parents=True, exist_ok=True)

        c = config.Config(
            filepath=Path(tmpdir) / "config.toml",
            context=Path(tmpdir),
            document=tomlkit.TOMLDocument(),
            registry=[],
            repository=config.ConfigRepository()
        )

        test_containerfile = versioned_context / "Containerfile"
        test_containerfile.touch(exist_ok=True)
        target_build = manifest.TargetBuild(
            manifest_context=image_context,
            config=c,
            target_data={"type": "std"},
            build_data={"version": "1.0.0"},
            image_name="test-image",
            version="1.0.0",
            type="std",
            build_os="Ubuntu 22.04",
        )
        assert target_build.containerfile_path == test_containerfile
        assert target_build.containerfile == test_containerfile.name

        test_containerfile = versioned_context / "Containerfile.ubuntu2204"
        test_containerfile.touch(exist_ok=True)
        target_build = manifest.TargetBuild(
            manifest_context=image_context,
            config=c,
            target_data={"type": "std"},
            build_data={"version": "1.0.0"},
            image_name="test-image",
            version="1.0.0",
            type="std",
            build_os="Ubuntu 22.04",
        )
        assert target_build.containerfile_path == test_containerfile
        assert target_build.containerfile == test_containerfile.name

        test_containerfile = versioned_context / "Containerfile.std"
        test_containerfile.touch(exist_ok=True)
        target_build = manifest.TargetBuild(
            manifest_context=image_context,
            config=c,
            target_data={"type": "std"},
            build_data={"version": "1.0.0"},
            image_name="test-image",
            version="1.0.0",
            type="std",
            build_os="Ubuntu 22.04",
        )
        assert target_build.containerfile_path == test_containerfile
        assert target_build.containerfile == test_containerfile.name

        test_containerfile = versioned_context / "Containerfile.ubuntu2204.std"
        test_containerfile.touch(exist_ok=True)
        target_build = manifest.TargetBuild(
            manifest_context=image_context,
            config=c,
            target_data={"type": "std"},
            build_data={"version": "1.0.0"},
            image_name="test-image",
            version="1.0.0",
            type="std",
            build_os="Ubuntu 22.04",
        )
        assert target_build.containerfile_path == test_containerfile
        assert target_build.containerfile == test_containerfile.name

    def test_containerfile_render(self, basic_manifest_obj, target_data_min, build_data):
        """Test that containerfiles with template rendering are resolved correctly"""
        target_build = manifest.TargetBuild(
            manifest_context=basic_manifest_obj.context,
            config=basic_manifest_obj.config,
            target_data=target_data_min,
            build_data=build_data,
            image_name=basic_manifest_obj.image_name,
            containerfile="Containerfile.{{ build.os | condense }}.{{ target.type }}",
            **build_data,
            **target_data_min,
        )
        assert target_build.containerfile == "Containerfile.ubuntu2204.min"
        assert target_build.containerfile_path == basic_manifest_obj.context / "1.0.0" / "Containerfile.ubuntu2204.min"

    def test_containerfile_not_found(self, basic_manifest_obj, target_data_min, build_data):
        """Test that a BakeryFileNotFoundError is raised when a containerfile is not found"""
        with pytest.raises(BakeryFileNotFoundError):
            build_data["os"] = "CentOS 7"
            manifest.TargetBuild(
                manifest_context=basic_manifest_obj.context,
                config=basic_manifest_obj.config,
                target_data=target_data_min,
                build_data=build_data,
                image_name=basic_manifest_obj.image_name,
                **build_data,
                **target_data_min,
            )

    def test_tags_default_resolution(self, basic_manifest_obj, target_data_min, target_data_std, build_data):
        basic_manifest_obj.config.registry = {config.ConfigRegistry(host="docker.io", namespace="posit")}

        target_build = manifest.TargetBuild(
            manifest_context=basic_manifest_obj.context,
            config=basic_manifest_obj.config,
            target_data=target_data_min,
            build_data=build_data,
            image_name=basic_manifest_obj.image_name,
            primary_os=True,
            **build_data,
            **target_data_min,
        )
        expected_tags = [
            "docker.io/posit/test-image:1.0.0-min",
            "docker.io/posit/test-image:1.0.0-ubuntu2204-min",
            "docker.io/posit/test-image:ubuntu2204-min",
            "docker.io/posit/test-image:latest-min",
        ]
        assert len(target_build.all_tags) == len(expected_tags)
        for tag in expected_tags:
            assert tag in target_build.all_tags

        target_build = manifest.TargetBuild(
            manifest_context=basic_manifest_obj.context,
            config=basic_manifest_obj.config,
            target_data=target_data_std,
            build_data=build_data,
            image_name=basic_manifest_obj.image_name,
            primary_os=True,
            **build_data,
            **target_data_std,
        )
        expected_tags = [
            "docker.io/posit/test-image:1.0.0",
            "docker.io/posit/test-image:1.0.0-ubuntu2204",
            "docker.io/posit/test-image:ubuntu2204",
            "docker.io/posit/test-image:latest",
        ]
        assert len(target_build.all_tags) == len(expected_tags)
        for tag in expected_tags:
            assert tag in target_build.all_tags

        build_data["latest"] = False
        target_build = manifest.TargetBuild(
            manifest_context=basic_manifest_obj.context,
            config=basic_manifest_obj.config,
            target_data=target_data_min,
            build_data=build_data,
            image_name=basic_manifest_obj.image_name,
            primary_os=True,
            **build_data,
            **target_data_min,
        )
        expected_tags = [
            "docker.io/posit/test-image:1.0.0-min",
            "docker.io/posit/test-image:1.0.0-ubuntu2204-min",
        ]
        assert len(target_build.all_tags) == len(expected_tags)
        for tag in expected_tags:
            assert tag in target_build.all_tags


        target_build = manifest.TargetBuild(
            manifest_context=basic_manifest_obj.context,
            config=basic_manifest_obj.config,
            target_data=target_data_std,
            build_data=build_data,
            image_name=basic_manifest_obj.image_name,
            primary_os=True,
            **build_data,
            **target_data_std,
        )
        expected_tags = [
            "docker.io/posit/test-image:1.0.0",
            "docker.io/posit/test-image:1.0.0-ubuntu2204",
        ]
        assert len(target_build.all_tags) == len(expected_tags)
        for tag in expected_tags:
            assert tag in target_build.all_tags

    def test_tags_render(self, basic_manifest_obj, target_data_min, build_data):
        tag_tpl = ["{{ build.version }}-dev"]
        latest_tag_tpl = ["latest-dev"]
        basic_manifest_obj.config.registry = {config.ConfigRegistry(host="docker.io", namespace="posit")}

        target_build = manifest.TargetBuild(
            manifest_context=basic_manifest_obj.context,
            config=basic_manifest_obj.config,
            target_data=target_data_min,
            build_data=build_data,
            image_name=basic_manifest_obj.image_name,
            tags=tag_tpl,
            latest_tags=latest_tag_tpl,
            **build_data,
            **target_data_min,
        )
        expected_tags = [
            "docker.io/posit/test-image:1.0.0-dev",
            "docker.io/posit/test-image:latest-dev",
        ]
        assert len(target_build.all_tags) == len(expected_tags)
        for tag in expected_tags:
            assert tag in target_build.all_tags

    def test_goss_default_resolution(self, basic_manifest_obj, target_data_std, build_data):
        target_build = manifest.TargetBuild(
            manifest_context=basic_manifest_obj.context,
            config=basic_manifest_obj.config,
            target_data=target_data_std,
            build_data=build_data,
            image_name=basic_manifest_obj.image_name,
            primary_os=True,
            **build_data,
            **target_data_std,
        )
        assert target_build.goss.deps == basic_manifest_obj.context / "1.0.0" / "deps"
        assert target_build.goss.test_path == basic_manifest_obj.context / "1.0.0" / "test"
        assert target_build.goss.command == "bash"
        assert target_build.goss.wait == 1

    def test_uid(self, basic_manifest_obj, target_data_std, build_data):
        target_build = manifest.TargetBuild(
            manifest_context=basic_manifest_obj.context,
            config=basic_manifest_obj.config,
            target_data=target_data_std,
            build_data=build_data,
            image_name=basic_manifest_obj.image_name,
            primary_os=True,
            **build_data,
            **target_data_std,
        )
        assert target_build.uid == "test-image-1-0-0-ubuntu2204-std"

    def test_labels(self, basic_manifest_obj, target_data_std, build_data):
        target_build = manifest.TargetBuild(
            manifest_context=basic_manifest_obj.context,
            config=basic_manifest_obj.config,
            target_data=target_data_std,
            build_data=build_data,
            image_name=basic_manifest_obj.image_name,
            primary_os=True,
            **build_data,
            **target_data_std,
        )
        assert target_build.labels["co.posit.image.name"] == "test-image"
        assert target_build.labels["co.posit.image.os"] == "Ubuntu 22.04"
        assert target_build.labels["co.posit.image.type"] == "std"
        assert target_build.labels["co.posit.image.version"] == "1.0.0"
        assert "org.opencontainers.image.created" in target_build.labels
        assert "org.opencontainers.image.revision" in target_build.labels
        assert target_build.labels["org.opencontainers.image.title"] == "test-image"
        assert target_build.labels["org.opencontainers.image.vendor"] == "Posit Software, PBC"
        assert target_build.labels["org.opencontainers.image.maintainer"] == "docker@posit.co"
        assert target_build.labels["org.opencontainers.image.authors"] == "Author 1 <author1@posit.co>, Author 2 <author2@posit.co>"
        assert target_build.labels["org.opencontainers.image.source"] == "github.com/rstudio/posit-images-shared"

    def test_hash(self, basic_manifest_obj, target_data_min, target_data_std, build_data):
        target_build_min = manifest.TargetBuild(
            manifest_context=basic_manifest_obj.context,
            config=basic_manifest_obj.config,
            target_data=target_data_min,
            build_data=build_data,
            image_name=basic_manifest_obj.image_name,
            primary_os=True,
            **build_data,
            **target_data_min,
        )
        target_build_std = manifest.TargetBuild(
            manifest_context=basic_manifest_obj.context,
            config=basic_manifest_obj.config,
            target_data=target_data_std,
            build_data=build_data,
            image_name=basic_manifest_obj.image_name,
            primary_os=True,
            **build_data,
            **target_data_std,
        )
        target_build_std2 = manifest.TargetBuild(
            manifest_context=basic_manifest_obj.context,
            config=basic_manifest_obj.config,
            target_data=target_data_std,
            build_data=build_data,
            image_name=basic_manifest_obj.image_name,
            primary_os=True,
            **build_data,
            **target_data_std,
        )
        assert hash(target_build_std) != hash(target_build_min)
        assert hash(target_build_std) == hash(target_build_std2)


class TestManifest:
    def test_manifest(self, basic_config_obj, basic_manifest_file):
        """Test creating a basic Manifest object does not raise an exception"""
        manifest.Manifest(
            filepath=basic_manifest_file,
            context=basic_manifest_file.parent,
            document=manifest.GenericTOMLModel.load_toml_file_data(basic_manifest_file),
            image_name="test-image",
            config=basic_config_obj,
        )

    def test_manifest_with_target_build(self, basic_config_obj, basic_manifest_file):
        """Test creating a basic Manifest object with a TargetBuild does not raise an exception"""
        data = manifest.GenericTOMLModel.load_toml_file_data(basic_manifest_file)
        target_build = manifest.TargetBuild(
            manifest_context=basic_manifest_file.parent,
            config=basic_config_obj,
            build_data=data["build"]["1.0.0"].unwrap(),
            target_data=data["target"]["min"].unwrap(),
            image_name="test-image",
            version="1.0.0",
            type="min",
            build_os="Ubuntu 22.04",
        )
        manifest.Manifest(
            filepath=basic_manifest_file,
            context=basic_manifest_file.parent,
            document=data,
            image_name="test-image",
            config=basic_config_obj,
            target_builds={target_build},
        )

    def test_load_file_with_config(self, basic_config_obj, basic_manifest_file, basic_expected_num_target_builds):
        """Test that the load_file_with_config method returns a Manifest object with expected data"""
        m = manifest.Manifest.load_file_with_config(basic_config_obj, basic_manifest_file)
        assert m.image_name == "test-image"
        assert m.config == basic_config_obj
        assert len(m.target_builds) == basic_expected_num_target_builds

    def test_filter_target_builds(self, basic_manifest_obj, basic_manifest_types, basic_manifest_os_plus_versions, basic_expected_num_target_builds):
        """Test the filter_target_builds method of a Manifest object"""
        target_builds = basic_manifest_obj.filter_target_builds(build_version="1.0.0")
        assert len(target_builds) == basic_expected_num_target_builds
        target_builds = basic_manifest_obj.filter_target_builds(target_type="min")
        assert len(target_builds) == len(basic_manifest_os_plus_versions)
        target_builds = basic_manifest_obj.filter_target_builds(target_type="std")
        assert len(target_builds) == len(basic_manifest_os_plus_versions)

    def test_types(self, basic_manifest_obj, basic_manifest_types, basic_expected_num_target_builds):
        """Test the types property of a Manifest object returns expected types"""
        assert len(basic_manifest_obj.types) == basic_expected_num_target_builds
        for _type in basic_manifest_types:
            assert _type in basic_manifest_obj.types

    def test_versions(self, basic_manifest_obj, basic_manifest_versions):
        """Test the versions property of a Manifest object returns expected versions"""
        assert len(basic_manifest_obj.versions) == len(basic_manifest_versions)
        for version in basic_manifest_versions:
            assert version in basic_manifest_obj.versions

    def test_generate_target_builds(self, basic_config_obj, basic_manifest_file, basic_expected_num_target_builds):
        """Test the generate_target_builds method of a Manifest object returns expected number of TargetBuild objects"""
        data = manifest.GenericTOMLModel.load_toml_file_data(basic_manifest_file)
        target_builds = manifest.Manifest.generate_target_builds(basic_config_obj, basic_manifest_file.parent, data)
        assert len(target_builds) == basic_expected_num_target_builds

    def test_guess_image_os_list(self, tmpdir):
        """Test the guess_image_os_list method of a Manifest object returns expected OS list"""
        files = [
            "Containerfile.ubuntu2204.min",
            "Containerfile.ubuntu2204.std",
            "Containerfile.ubuntu2404.min",
            "Containerfile.ubuntu2404.std",
            "Containerfile.centos7.min",
            "Containerfile.centos7.std",
            "Containerfile.rockylinux8.min",
            "Containerfile.rockylinux8.std",
        ]
        t = Path(tmpdir)
        for f in files:
            (t / f).touch(exist_ok=True)
        os_list = manifest.Manifest.guess_image_os_list(t)
        assert len(os_list) == 4
        assert "Ubuntu 2204" in os_list
        assert "Ubuntu 2404" in os_list
        assert "Centos 7" in os_list
        assert "Rockylinux 8" in os_list

    def test_append_build_version(self, basic_manifest_obj):
        """Test append_build_version updates the manifest document with a new version"""
        basic_manifest_obj.guess_image_os_list = MagicMock(return_value=["Ubuntu 2204"])
        basic_manifest_obj.append_build_version("1.0.1")
        assert "1.0.1" in basic_manifest_obj.document["build"]
        assert basic_manifest_obj.document["build"]["1.0.1"]["latest"] is True
        assert basic_manifest_obj.document["build"]["1.0.1"]["os"] == ["Ubuntu 2204"]
        assert "1.0.0" in basic_manifest_obj.document["build"]
        assert "latest" not in basic_manifest_obj.document["build"]["1.0.0"]

    def test_append_build_version_not_latest(self, basic_manifest_obj):
        """Test that mark_latest=False does not set the new version as the latest for append_build_version"""
        basic_manifest_obj.guess_image_os_list = MagicMock(return_value=["Ubuntu 2204"])
        basic_manifest_obj.append_build_version("1.0.1", mark_latest=False)
        assert "1.0.1" in basic_manifest_obj.document["build"]
        assert "latest" not in basic_manifest_obj.document["build"]["1.0.1"]
        assert basic_manifest_obj.document["build"]["1.0.1"]["os"] == ["Ubuntu 2204"]
        assert "1.0.0" in basic_manifest_obj.document["build"]
        assert basic_manifest_obj.document["build"]["1.0.0"]["latest"] is True

    def test_render_image_template(self, basic_tmpcontext):
        """Test rendering the image template for a new version creates the expected files"""
        config_file = basic_tmpcontext / "config.toml"
        c = config.Config.load_file(config_file)
        image_dir = basic_tmpcontext / "test-image"
        m = manifest.Manifest.load_file_with_config(c, image_dir / "manifest.toml")
        m.render_image_template("1.0.1")
        new_version_dir = image_dir / "1.0.1"
        assert new_version_dir.exists()
        assert (new_version_dir / "deps").exists()
        assert (new_version_dir / "deps" / "ubuntu2204_packages.txt").exists()
        assert (new_version_dir / "deps" / "ubuntu2204_optional_packages.txt").exists()
        assert (new_version_dir / "test").exists()
        assert (new_version_dir / "test" / "goss.yaml").exists()
        assert (new_version_dir / "Containerfile.ubuntu2204.min").exists()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (new_version_dir / "Containerfile.ubuntu2204.min").read_text()
        assert 'ubuntu2204_optional_packages.txt' not in (new_version_dir / "Containerfile.ubuntu2204.min").read_text()
        assert (new_version_dir / "Containerfile.ubuntu2204.std").exists()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (new_version_dir / "Containerfile.ubuntu2204.std").read_text()
        assert 'ubuntu2204_optional_packages.txt' in (new_version_dir / "Containerfile.ubuntu2204.std").read_text()

    def test_new_version(self, basic_tmpcontext):
        """Test creating a new version of an image creates the expected files and updates the manifest"""
        config_file = basic_tmpcontext / "config.toml"
        c = config.Config.load_file(config_file)
        image_dir = basic_tmpcontext / "test-image"
        m = manifest.Manifest.load_file_with_config(c, image_dir / "manifest.toml")
        m.new_version("1.0.1")
        new_version_dir = image_dir / "1.0.1"

        assert new_version_dir.exists()
        assert (new_version_dir / "deps").exists()
        assert (new_version_dir / "deps" / "ubuntu2204_packages.txt").exists()
        assert (new_version_dir / "deps" / "ubuntu2204_optional_packages.txt").exists()
        assert (new_version_dir / "test").exists()
        assert (new_version_dir / "test" / "goss.yaml").exists()
        assert (new_version_dir / "Containerfile.ubuntu2204.min").exists()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (new_version_dir / "Containerfile.ubuntu2204.min").read_text()
        assert 'ubuntu2204_optional_packages.txt' not in (new_version_dir / "Containerfile.ubuntu2204.min").read_text()
        assert (new_version_dir / "Containerfile.ubuntu2204.std").exists()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (new_version_dir / "Containerfile.ubuntu2204.std").read_text()
        assert 'ubuntu2204_optional_packages.txt' in (new_version_dir / "Containerfile.ubuntu2204.std").read_text()

        assert "1.0.1" in m.versions
        assert len(m.target_builds) == 4

        with open(image_dir / "manifest.toml", "rb") as f:
            d = tomlkit.loads(f.read())
        assert "1.0.1" in d["build"]
        assert d["build"]["1.0.1"]["latest"] is True
        assert d["build"]["1.0.1"]["os"] == ["Ubuntu 2204"]

    def test_new_version_no_save(self, basic_tmpcontext):
        """Test save=False does not update the manifest file when creating a new version"""
        config_file = basic_tmpcontext / "config.toml"
        c = config.Config.load_file(config_file)
        image_dir = basic_tmpcontext / "test-image"
        m = manifest.Manifest.load_file_with_config(c, image_dir / "manifest.toml")
        m.new_version("1.0.1", save=False)
        new_version_dir = image_dir / "1.0.1"

        assert new_version_dir.exists()
        assert (new_version_dir / "deps").exists()
        assert (new_version_dir / "deps" / "ubuntu2204_packages.txt").exists()
        assert (new_version_dir / "deps" / "ubuntu2204_optional_packages.txt").exists()
        assert (new_version_dir / "test").exists()
        assert (new_version_dir / "test" / "goss.yaml").exists()
        assert (new_version_dir / "Containerfile.ubuntu2204.min").exists()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (new_version_dir / "Containerfile.ubuntu2204.min").read_text()
        assert 'ubuntu2204_optional_packages.txt' not in (new_version_dir / "Containerfile.ubuntu2204.min").read_text()
        assert (new_version_dir / "Containerfile.ubuntu2204.std").exists()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (new_version_dir / "Containerfile.ubuntu2204.std").read_text()
        assert 'ubuntu2204_optional_packages.txt' in (new_version_dir / "Containerfile.ubuntu2204.std").read_text()

        assert "1.0.1" in m.versions
        assert len(m.target_builds) == 4

        with open(image_dir / "manifest.toml", "rb") as f:
            d = tomlkit.loads(f.read())
        assert "1.0.1" not in d["build"]
        assert d["build"]["1.0.0"]["latest"] is True
