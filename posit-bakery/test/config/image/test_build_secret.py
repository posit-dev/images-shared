import pytest
from pydantic import ValidationError

from posit_bakery.config.image.build_secret import BuildSecret

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


class TestBuildSecret:
    def test_required_fields(self):
        """Both id and envVar are required."""
        with pytest.raises(ValidationError, match="id"):
            BuildSecret(envVar="GITHUB_TOKEN")
        with pytest.raises(ValidationError, match="envVar"):
            BuildSecret(id="github_token")

    def test_empty_strings_rejected(self):
        """Empty id or envVar is not a valid secret."""
        with pytest.raises(ValidationError):
            BuildSecret(id="", envVar="GITHUB_TOKEN")
        with pytest.raises(ValidationError):
            BuildSecret(id="github_token", envVar="")

    def test_as_cli_option(self):
        """as_cli_option returns the docker --secret flag value."""
        secret = BuildSecret(id="github_token", envVar="GITHUB_TOKEN")
        assert secret.as_cli_option() == "id=github_token,env=GITHUB_TOKEN"