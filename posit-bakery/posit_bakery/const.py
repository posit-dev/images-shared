from enum import Enum


class DevVersionInclusionEnum(str, Enum):
    """Enum for development versions inclusion."""

    INCLUDE = "include"
    EXCLUDE = "exclude"
    ONLY = "only"


class MatrixVersionInclusionEnum(str, Enum):
    """Enum for version inclusion in matrix."""

    INCLUDE = "include"
    EXCLUDE = "exclude"
    ONLY = "only"


class GetTagsOutputFormat(str, Enum):
    """Output format for get tags command."""

    COMPONENT = "component"
    UID = "uid"


REGEX_FULL_IMAGE_TAG_PATTERN = (
    r"^(?P<repository>[\w.\-_]+((?::\d+|)(?=/[a-z0-9._-]+/[a-z0-9._-]+))|)"
    r"(?:/|)(?P<image>[a-z0-9.\-_]+(?:/[a-z0-9.\-_]+|))(:(?P<tag>[\w.\-_]{1,127})|)$"
)
REGEX_IMAGE_TAG_SUFFIX_ALLOWED_CHARACTERS_PATTERN = r"[^a-zA-Z0-9_\-.]"

DEFAULT_BASE_IMAGE = "docker.io/library/ubuntu:22.04"
POSIT_LABEL_PREFIX = "co.posit.image"
OCI_LABEL_PREFIX = "org.opencontainers.image"

JINJA2_TEMPLATE_EXTENSIONS = {".jinja2", ".j2", ".jinja"}

DEFAULT_MAX_CONCURRENCY = 4

# Bounds a single tracked command (e.g. an oras/soci invocation) so a hung registry
# call can't block a publish run forever; 30 minutes comfortably covers slow pushes
# of large image layers without masking a truly stuck process.
DEFAULT_COMMAND_TIMEOUT_SECONDS = 1800.0
