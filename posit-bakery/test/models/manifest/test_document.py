from pathlib import Path

import pytest
from pydantic import ValidationError
from ruamel.yaml import YAML

from posit_bakery.models.manifest.document import ManifestDocument
from test.helpers import yaml_file_testcases


@pytest.mark.manifest
@pytest.mark.schema
class TestManifestDocument:
    def test_empty_init(self):
        """Creating an empty ManifestDocument fails validation"""
        with pytest.raises(ValidationError):
            ManifestDocument()

    @pytest.mark.parametrize("yaml_file", yaml_file_testcases("manifest", "valid"))
    def test_valid(self, caplog, yaml_file: Path):
        """Test valid YAML manifest files

        Files are stored in test/testdata/manifest/valid
        """
        y = YAML()
        doc = y.load(yaml_file)

        ManifestDocument(**doc)

        assert "WARNING" not in caplog.text

    @pytest.mark.parametrize("yaml_file", yaml_file_testcases("manifest", "valid-with-warning"))
    def test_valid_with_warning(self, caplog, yaml_file: Path):
        """Test valid YAML manifest files, but raise warnings in the validation

        Files are stored in test/testdata/manifest/valid-with-warning
        """
        y = YAML()
        doc = y.load(yaml_file)

        ManifestDocument(**doc)

        assert "WARNING" in caplog.text

    @pytest.mark.parametrize("yaml_file", yaml_file_testcases("manifest", "invalid"))
    def test_invalid(self, yaml_file: Path):
        """Test invalid YAML manifest files

        Files are stored in test/testdata/manifest/invalid
        """
        y = YAML()
        doc = y.load(yaml_file) or {}

        with pytest.raises(ValidationError):
            ManifestDocument(**doc)

    @pytest.mark.parametrize(
        "image_name",
        [
            ("test.image"),
            ("test_image"),
            ("-image"),
            ("4-image"),
            ("Test-Image"),
            ("test-image-1"),
            ("test$image"),
            ("test-image@this"),
            ("image-name:latest"),
        ],
    )
    def test_invalid_image_name(self, image_name: str):
        """Test invalid image names raise a ValidationError

        Ensures that image names match the expected format
        """
        with pytest.raises(ValidationError):
            ManifestDocument(image_name=image_name)
