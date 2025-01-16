from pathlib import Path

import pytest
import tomlkit
from pydantic import ValidationError

from posit_bakery.models import ManifestDocument
from ..helpers import toml_file_testcases


@pytest.mark.manifest
@pytest.mark.schema
class TestManifestDocument:
    def test_empty_init(self):
        """Creating an empty ManifestDocument fails validation"""
        with pytest.raises(ValidationError):
            ManifestDocument()

    @pytest.mark.parametrize("toml_file", toml_file_testcases("manifest", "valid"))
    def test_valid(self, caplog, toml_file: Path):
        """Test valid TOML manifest files

        Files are stored in test/testdata/manifest/valid
        """
        with open(toml_file, "r") as f:
            doc = tomlkit.load(f)

        ManifestDocument(**doc.unwrap())

        assert "WARNING" not in caplog.text

    @pytest.mark.parametrize("toml_file", toml_file_testcases("manifest", "valid-with-warning"))
    def test_valid_with_warning(self, caplog, toml_file: Path):
        """Test valid TOML manifest files, but raise warnings in the validation

        Files are stored in test/testdata/manifest/valid-with-warning
        """
        with open(toml_file, "r") as f:
            doc = tomlkit.load(f)

        ManifestDocument(**doc.unwrap())

        assert "WARNING" in caplog.text

    @pytest.mark.parametrize("toml_file", toml_file_testcases("manifest", "invalid"))
    def test_invalid(self, toml_file: Path):
        """Test invalid TOML manifest files

        Files are stored in test/testdata/manifest/invalid
        """
        with open(toml_file, "r") as f:
            doc = tomlkit.load(f)

        with pytest.raises(ValidationError):
            ManifestDocument(**doc.unwrap())

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
