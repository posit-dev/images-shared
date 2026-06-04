import re
from enum import Enum

CALVER_REGEX_PATTERN = re.compile(
    r"(0|[1-9]\d*)\.([0-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)
# Environment variable pattern: $VAR or ${VAR}
_ENV_VAR = r"\$\{?[a-zA-Z_][a-zA-Z0-9_]*\}?"

# Character classes for different URL components
_HOST = r"[a-zA-Z0-9\-._~%]"
_PORT = r"[0-9]{1,5}"
_PATH = r"[a-zA-Z0-9\-._~%:@!$&'()*+,;=/]"
_QUERY_FRAGMENT = r"[a-zA-Z0-9\-._~%:@!$&'()*+,;=/?]"

# URL pattern: protocol://host[:port][/path][?query][#fragment]
# Each component can contain its allowed characters or an environment variable
URL_WITH_ENV_VARS_REGEX_PATTERN = re.compile(
    rf"^https?://(?:{_HOST}|{_ENV_VAR})+"
    rf"(?::(?:{_PORT}|{_ENV_VAR}))?"
    rf"(?:/(?:{_PATH}|{_ENV_VAR})*)?"
    rf"(?:\?(?:{_QUERY_FRAGMENT}|{_ENV_VAR})*)?"
    rf"(?:#(?:{_QUERY_FRAGMENT}|{_ENV_VAR})*)?$"
)

WORKBENCH_DAILY_URL = "https://dailies.rstudio.com/rstudio/{release_branch}/index.json"
PACKAGE_MANAGER_DAILY_URL = "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm-main-latest.txt"
PACKAGE_MANAGER_PREVIEW_URL = "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm-rc-latest.txt"
CONNECT_DAILY_URL = "https://cdn.posit.co/connect/latest-packages.json"
POSITRON_DAILY_CDN_URL_TEMPLATE = "https://cdn.posit.co/positron/dailies/pwb/{positron_cdn_arch}/releases.json"
DOWNLOADS_JSON_URL = "https://posit.co/wp-content/uploads/downloads.json"


class ProductEnum(str, Enum):
    CONNECT = "connect"
    PACKAGE_MANAGER = "package-manager"
    WORKBENCH = "workbench"
    WORKBENCH_SESSION = "workbench-session"
    POSITRON = "positron"


class ReleaseChannelEnum(str, Enum):
    RELEASE = "release"
    PREVIEW = "preview"
    DAILY = "daily"


ReleaseStreamEnum = ReleaseChannelEnum  # deprecated alias, remove in Phase 0.5c


PRODUCT_RELEASE_CHANNEL_SUPPORT_MAP = {
    ProductEnum.CONNECT: [ReleaseChannelEnum.RELEASE, ReleaseChannelEnum.DAILY],
    ProductEnum.PACKAGE_MANAGER: [ReleaseChannelEnum.RELEASE, ReleaseChannelEnum.PREVIEW, ReleaseChannelEnum.DAILY],
    ProductEnum.WORKBENCH: [ReleaseChannelEnum.RELEASE, ReleaseChannelEnum.DAILY],
    ProductEnum.POSITRON: [ReleaseChannelEnum.DAILY],
}

PRODUCT_RELEASE_STREAM_SUPPORT_MAP = PRODUCT_RELEASE_CHANNEL_SUPPORT_MAP  # deprecated alias, remove in Phase 0.5c
