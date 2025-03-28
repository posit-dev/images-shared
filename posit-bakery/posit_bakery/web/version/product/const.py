import re
from enum import Enum

SEMVER_REGEX_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


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
    ProductEnum.WORKBENCH: [ReleaseStreamEnum.RELEASE, ReleaseStreamEnum.PREVIEW, ReleaseStreamEnum.DAILY],
}
