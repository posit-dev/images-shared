from unittest.mock import MagicMock

import pytest
import tomlkit

from posit_bakery.models import Config, Manifest
from posit_bakery.models.generic import GenericTOMLModel

pytestmark = [
    pytest.mark.unit,
    pytest.mark.manifest,
]


class TestManifest:
    def test_manifest(self, basic_config_obj, basic_manifest_file):
        """Test creating a basic Manifest object does not raise an exception"""
        Manifest(
            filepath=basic_manifest_file,
            context=basic_manifest_file.parent,
            document=GenericTOMLModel.read(basic_manifest_file),
            image_name="test-image",
            config=basic_config_obj,
        )

    def test_load(self, basic_manifest_file, basic_expected_num_variants):
        """Test that the load_file_with_config method returns a Manifest object with expected data"""
        m = Manifest.load(basic_manifest_file)

        assert m.context == basic_manifest_file.parent
        assert m.filepath == basic_manifest_file
        assert m.model.image_name == "test-image"
        assert len(m.model.build) == 1
        assert len(m.model.target) == 2

    def test_types(self, basic_manifest_obj, basic_manifest_types, basic_expected_num_variants):
        """Test the types property of a Manifest object returns expected types"""
        assert len(basic_manifest_obj.types) == basic_expected_num_variants
        for _type in basic_manifest_types:
            assert _type in basic_manifest_obj.types

    def test_versions(self, basic_manifest_obj, basic_manifest_versions):
        """Test the versions property of a Manifest object returns expected versions"""
        assert len(basic_manifest_obj.versions) == len(basic_manifest_versions)
        for version in basic_manifest_versions:
            assert version in basic_manifest_obj.versions


@pytest.mark.skip("TODO: Move the new actions into the Image* objects")
class TestManifestUpdate:
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

    def test_new_version(self, basic_tmpcontext):
        """Test creating a new version of an image creates the expected files and updates the manifest"""
        config_file = basic_tmpcontext / "config.toml"
        c = Config.load(config_file)
        image_dir = basic_tmpcontext / "test-image"
        m = Manifest.load(c, image_dir / "manifest.toml")
        m.new_version("1.0.1")
        new_version_dir = image_dir / "1.0.1"

        assert new_version_dir.is_dir()
        assert (new_version_dir / "deps").is_dir()
        assert (new_version_dir / "deps" / "ubuntu2204_packages.txt").is_file()
        assert (new_version_dir / "deps" / "ubuntu2204_optional_packages.txt").is_file()
        assert (new_version_dir / "test").is_dir()
        assert (new_version_dir / "test" / "goss.yaml").is_file()
        assert (new_version_dir / "Containerfile.ubuntu2204.min").is_file()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (new_version_dir / "Containerfile.ubuntu2204.min").read_text()
        assert "ubuntu2204_optional_packages.txt" not in (new_version_dir / "Containerfile.ubuntu2204.min").read_text()
        assert (new_version_dir / "Containerfile.ubuntu2204.std").is_file()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (new_version_dir / "Containerfile.ubuntu2204.std").read_text()
        assert "ubuntu2204_optional_packages.txt" in (new_version_dir / "Containerfile.ubuntu2204.std").read_text()

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
        c = Config.load(config_file)
        image_dir = basic_tmpcontext / "test-image"
        m = Manifest.load(c, image_dir / "manifest.toml")
        m.new_version("1.0.1", save=False)
        new_version_dir = image_dir / "1.0.1"

        assert new_version_dir.is_dir()
        assert (new_version_dir / "deps").is_dir()
        assert (new_version_dir / "deps" / "ubuntu2204_packages.txt").is_file()
        assert (new_version_dir / "deps" / "ubuntu2204_optional_packages.txt").is_file()
        assert (new_version_dir / "test").is_dir()
        assert (new_version_dir / "test" / "goss.yaml").is_file()
        assert (new_version_dir / "Containerfile.ubuntu2204.min").is_file()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (new_version_dir / "Containerfile.ubuntu2204.min").read_text()
        assert "ubuntu2204_optional_packages.txt" not in (new_version_dir / "Containerfile.ubuntu2204.min").read_text()
        assert (new_version_dir / "Containerfile.ubuntu2204.std").is_file()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (new_version_dir / "Containerfile.ubuntu2204.std").read_text()
        assert "ubuntu2204_optional_packages.txt" in (new_version_dir / "Containerfile.ubuntu2204.std").read_text()

        assert "1.0.1" in m.versions
        assert len(m.target_builds) == 4

        with open(image_dir / "manifest.toml", "rb") as f:
            d = tomlkit.loads(f.read())
        assert "1.0.1" not in d["build"]
        assert d["build"]["1.0.0"]["latest"] is True
