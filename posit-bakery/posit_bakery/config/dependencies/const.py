# All available python versions from astral-sh/python-build-standalone
import enum

from ruamel.yaml import yaml_object, YAML

yaml = YAML()

UV_PYTHON_DOWNLOADS_JSON_URL = (
    "https://raw.githubusercontent.com/astral-sh/uv/refs/heads/main/crates/uv-python/download-metadata.json"
)

# All available R versions from Posit
R_VERSIONS_URL = "https://cdn.posit.co/r/versions.json"

# Most recent patch release of Quarto
QUARTO_DOWNLOAD_URL = "https://quarto.org/docs/download/_download.json"
# Most recent patch of prerelease Quarto
QUARTO_PRERELEASE_URL = "https://quarto.org/docs/download/_prerelease.json"
# Most recent patch of older Quarto minor versions
QUARTO_PREVIOUS_VERSIONS_URL = (
    "https://raw.githubusercontent.com/quarto-dev/quarto-web/refs/heads/main/docs/download/_download-older.yml"
)

# All available Positron releases for Workbench
# The URL contains an architecture segment: x86_64 or arm64.
# TARGETARCH (amd64/arm64) must be mapped to the URL architecture.
POSITRON_ARCH_MAP = {"amd64": "x86_64", "arm64": "arm64"}
POSITRON_DEFAULT_ARCH = "amd64"
POSITRON_RELEASES_URL_TEMPLATE = "https://cdn.posit.co/positron/releases/pwb/{arch}/all-releases.json"


@yaml_object(yaml)
class SupportedDependencies(enum.StrEnum):
    PYTHON = "python"
    R = "R"
    QUARTO = "quarto"
    POSITRON = "positron"

    @classmethod
    def to_yaml(cls, representer, node):
        return representer.represent_str(node.value)
