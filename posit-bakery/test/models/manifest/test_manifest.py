from unittest.mock import MagicMock

import pytest
import tomlkit

from posit_bakery.models import Config, Manifest
from posit_bakery.models.toml.generic import GenericTOMLModel

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
