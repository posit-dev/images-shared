from pathlib import Path

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
        manifest.Manifest(
            filepath=basic_manifest_file,
            context=basic_manifest_file.parent,
            document=manifest.GenericTOMLModel.load_toml_file_data(basic_manifest_file),
            image_name="test-image",
            config=basic_config_obj,
        )


