from pathlib import Path

import pytest
from pydantic import ValidationError
from ruamel.yaml import YAML

from posit_bakery.models.config.document import ConfigDocument
from test.helpers import yaml_file_testcases


@pytest.mark.config
@pytest.mark.schema
class TestConfigDocument:
    def test_empty_init(self):
        """Creating an empty ConfigDocument fails validation"""
        with pytest.raises(ValidationError):
            ConfigDocument()

    def test_basic_doc(self, basic_config_file):
        """Read basic/config.yaml and validate the document"""
        y = YAML()
        doc = y.load(basic_config_file)

        ConfigDocument(**doc)

    @pytest.mark.parametrize("yaml_file", yaml_file_testcases("config", "valid"))
    def test_valid(self, caplog, yaml_file: Path):
        """Test valid YAML config files

        Files are stored in test/testdata/config/valid
        """
        y = YAML()
        doc = y.load(yaml_file)

        ConfigDocument(**doc)

        assert "WARNING" not in caplog.text

    @pytest.mark.parametrize("yaml_file", yaml_file_testcases("config", "valid-with-warning"))
    def test_valid_with_warning(self, caplog, yaml_file: Path):
        """Test valid YAML config files, but raise warnings in the validation

        Files are stored in test/testdata/config/valid-with-warning
        """
        y = YAML()
        doc = y.load(yaml_file)

        ConfigDocument(**doc)

        assert "WARNING" in caplog.text

    @pytest.mark.parametrize("yaml_file", yaml_file_testcases("config", "invalid"))
    def test_invalid(self, yaml_file: Path):
        """Test invalid YAML config files

        Files are stored in test/testdata/config/invalid
        """
        y = YAML()
        doc = y.load(yaml_file) or {}

        with pytest.raises(ValidationError):
            ConfigDocument(**doc)
