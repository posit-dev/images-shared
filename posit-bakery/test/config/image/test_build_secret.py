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

    def test_as_bake_json(self):
        """as_bake_json returns the per-target secret entry for a Docker Bake JSON plan."""
        secret = BuildSecret(id="github_token", envVar="GITHUB_TOKEN")
        assert secret.as_bake_json() == {"type": "env", "id": "github_token", "env": "GITHUB_TOKEN"}

    @pytest.mark.parametrize(
        "id_value",
        [
            "github_token",
            "github-token",
            "github.token",
            "GitHub_Token",
            "tok3n",
            "_leading_underscore",
        ],
    )
    def test_valid_id_patterns(self, id_value):
        """Valid id values: alphanumerics, underscores, dots, and hyphens."""
        secret = BuildSecret(id=id_value, envVar="GITHUB_TOKEN")
        assert secret.id == id_value

    @pytest.mark.parametrize(
        "id_value",
        [
            "-leading-hyphen",
            ".leading.dot",
            "has space",
            "has,comma",
            "has=equals",
            "has/slash",
            "has;semicolon",
            "has$dollar",
            "has`backtick",
            "has\nnewline",
            "id,src=/etc/passwd",
        ],
    )
    def test_invalid_id_patterns_rejected(self, id_value):
        """Invalid id values that could enable CLI injection are rejected."""
        with pytest.raises(ValidationError, match="id"):
            BuildSecret(id=id_value, envVar="GITHUB_TOKEN")

    @pytest.mark.parametrize(
        "env_value",
        [
            "GITHUB_TOKEN",
            "github_token",
            "_LEADING_UNDERSCORE",
            "TOKEN_2",
            "X",
        ],
    )
    def test_valid_env_var_patterns(self, env_value):
        """Valid envVar values follow POSIX env var name rules."""
        secret = BuildSecret(id="github_token", envVar=env_value)
        assert secret.envVar == env_value

    @pytest.mark.parametrize(
        "env_value",
        [
            "1LEADING_DIGIT",
            "HAS-HYPHEN",
            "HAS.DOT",
            "HAS SPACE",
            "HAS,COMMA",
            "HAS=EQUALS",
            "HAS$DOLLAR",
            "HAS`BACKTICK",
            "HAS\nNEWLINE",
            "TOKEN,src=/etc/passwd",
        ],
    )
    def test_invalid_env_var_patterns_rejected(self, env_value):
        """Invalid envVar values that could enable CLI injection are rejected."""
        with pytest.raises(ValidationError, match="envVar"):
            BuildSecret(id="github_token", envVar=env_value)
