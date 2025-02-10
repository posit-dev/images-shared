from pathlib import Path
from unittest.mock import patch

import jinja2
import tomlkit

from posit_bakery.templating import TPL_CONFIG_TOML
from posit_bakery.templating.default import create_project_config


class TestCreateProjectConfig:
    def test_create(self, caplog, tmpdir):
        """Test creating a project config.toml file from  template"""
        config_file = Path(tmpdir) / "config.toml"
        assert not config_file.exists()
        create_project_config(config_file)
        assert config_file.exists()
        contents = config_file.read_text()
        expected_contents = jinja2.Environment().from_string(TPL_CONFIG_TOML).render(repo_url="<REPLACE ME>")
        assert tomlkit.loads(contents) == tomlkit.loads(expected_contents)
        assert "WARNING" in caplog.text
        assert "Unable to determine repository name" in caplog.text

    def test_patched_get_repo(self, tmpdir):
        """Test creating a project config.toml file from template with patched get_repo_url"""
        fake_repo_url = "github.com/posit-dev/images-test"
        config_file = Path(tmpdir) / "config.toml"
        assert not config_file.exists()
        with patch("posit_bakery.templating.default.util.try_get_repo_url", return_value=fake_repo_url):
            create_project_config(config_file)
        assert config_file.exists()
        contents = config_file.read_text()
        expected_contents = jinja2.Environment().from_string(TPL_CONFIG_TOML).render(repo_url=fake_repo_url)
        assert tomlkit.loads(contents) == tomlkit.loads(expected_contents)
