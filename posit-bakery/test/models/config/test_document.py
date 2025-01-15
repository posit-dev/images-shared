from pathlib import Path

import pytest
import tomlkit
from pydantic import ValidationError

from posit_bakery.models.config.document import ConfigDocument
from ..helpers import toml_file_testcases


@pytest.mark.config
@pytest.mark.schema
class TestConfigDocument:
    def test_empty_init(self):
        """Creating an empty ConfigDocument fails validation"""
        with pytest.raises(ValidationError):
            ConfigDocument()

    def test_basic_doc(self, basic_config_file):
        """Read basic/config.toml and validate the document"""
        with open(basic_config_file, "r") as f:
            doc = tomlkit.load(f)

            ConfigDocument(**doc.unwrap())

    @pytest.mark.parametrize("toml_file", toml_file_testcases("config", "valid"))
    def test_valid(self, caplog, toml_file: Path):
        """Test valid TOML config files

        Files are stored in test/testdata/config/valid
        """
        with open(toml_file, "r") as f:
            doc = tomlkit.load(f)

        ConfigDocument(**doc.unwrap())

        assert "WARNING" not in caplog.text

    @pytest.mark.parametrize("toml_file", toml_file_testcases("config", "valid-with-warning"))
    def test_valid_with_warning(self, caplog, toml_file: Path):
        """Test valid TOML config files, but raise warnings in the validation

        Files are stored in test/testdata/config/valid-with-warning
        """
        with open(toml_file, "r") as f:
            doc = tomlkit.load(f)

        ConfigDocument(**doc.unwrap())

        assert "WARNING" in caplog.text

    @pytest.mark.parametrize("toml_file", toml_file_testcases("config", "invalid"))
    def test_invalid(self, toml_file: Path):
        """Test invalid TOML config files

        Files are stored in test/testdata/config/invalid
        """
        with open(toml_file, "r") as f:
            doc = tomlkit.load(f)

        with pytest.raises(ValidationError):
            ConfigDocument(**doc.unwrap())
