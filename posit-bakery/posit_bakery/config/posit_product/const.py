import re
from enum import Enum

CALVER_REGEX_PATTERN = re.compile(
    r"(0|[1-9]\d*)\.([0-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?"
)

WORKBENCH_DAILY_URL = "https://dailies.rstudio.com/rstudio/latest/index.json"
PACKAGE_MANAGER_DAILY_URL = "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm-main-latest.txt"
PACKAGE_MANAGER_PREVIEW_URL = "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm-rc-latest.txt"
CONNECT_DAILY_URL = "https://cdn.posit.co/connect/latest-packages.json"
DOWNLOADS_JSON_URL = "https://posit.co/wp-content/uploads/downloads.json"


class ProductEnum(str, Enum):
    CONNECT = "connect"
    PACKAGE_MANAGER = "package-manager"
    WORKBENCH = "workbench"
    WORKBENCH_SESSION = "workbench-session"


class ReleaseStreamEnum(str, Enum):
    RELEASE = "release"
    PREVIEW = "preview"
    DAILY = "daily"


PRODUCT_RELEASE_STREAM_SUPPORT_MAP = {
    ProductEnum.CONNECT: [ReleaseStreamEnum.RELEASE, ReleaseStreamEnum.DAILY],
    ProductEnum.PACKAGE_MANAGER: [ReleaseStreamEnum.RELEASE, ReleaseStreamEnum.PREVIEW, ReleaseStreamEnum.DAILY],
    ProductEnum.WORKBENCH: [
        ReleaseStreamEnum.RELEASE,
        # FIXME: This stream seems out of date
        # ReleaseStreamEnum.PREVIEW,
        ReleaseStreamEnum.DAILY,
    ],
}
