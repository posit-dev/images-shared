from enum import Enum

from pydantic import BaseModel

from posit_bakery.config.shared import OSFamilyEnum


class TargetPlatform(str, Enum):
    LINUX_AMD64 = "linux/amd64"
    LINUX_ARM64 = "linux/arm64"


DEFAULT_PLATFORMS = [TargetPlatform.LINUX_AMD64]


class BuildOS(BaseModel):
    family: OSFamilyEnum
    name: str
    version: str
    codename: str | None = None

    @property
    def majorVersion(self) -> str:
        return self.version.split(".")[0]

    @property
    def packageSuffix(self) -> str:
        if self.family == OSFamilyEnum.DEBIAN_LIKE:
            return "deb"
        elif self.family == OSFamilyEnum.REDHAT_LIKE or self.family == OSFamilyEnum.SUSE_LIKE:
            return "rpm"
        return ""

    @property
    def packageArchSeparator(self) -> str:
        if self.family == OSFamilyEnum.REDHAT_LIKE or self.family == OSFamilyEnum.SUSE_LIKE:
            return "."
        return "_"

    @property
    def packageVersionSeparator(self) -> str:
        if self.family == OSFamilyEnum.REDHAT_LIKE or self.family == OSFamilyEnum.SUSE_LIKE:
            return "-"
        return "_"


ALTERNATE_NAMES = {
    "redhat": "rhel",
    "red hat": "rhel",
    "rh": "rhel",
    "el": "rhel",
    "almalinux": "alma",
    "alma linux": "alma",
    "rockylinux": "rocky",
    "rocky linux": "rocky",
}


SUPPORTED_OS = {
    "ubuntu": {
        "24": BuildOS(family=OSFamilyEnum.DEBIAN_LIKE, name="ubuntu", version="24.04", codename="noble"),
        "22": BuildOS(family=OSFamilyEnum.DEBIAN_LIKE, name="ubuntu", version="22.04", codename="jammy"),
    },
    "debian": {
        "13": BuildOS(family=OSFamilyEnum.DEBIAN_LIKE, name="debian", version="13", codename="trixie"),
        "12": BuildOS(family=OSFamilyEnum.DEBIAN_LIKE, name="debian", version="12", codename="bookworm"),
        "11": BuildOS(family=OSFamilyEnum.DEBIAN_LIKE, name="debian", version="11", codename="bullseye"),
    },
    "rhel": {
        "10": BuildOS(family=OSFamilyEnum.REDHAT_LIKE, name="rhel", version="10"),
        "9": BuildOS(family=OSFamilyEnum.REDHAT_LIKE, name="rhel", version="9"),
        "8": BuildOS(family=OSFamilyEnum.REDHAT_LIKE, name="rhel", version="8"),
    },
    "alma": {
        "10": BuildOS(family=OSFamilyEnum.REDHAT_LIKE, name="alma", version="10"),
        "9": BuildOS(family=OSFamilyEnum.REDHAT_LIKE, name="alma", version="9"),
        "8": BuildOS(family=OSFamilyEnum.REDHAT_LIKE, name="alma", version="8"),
    },
    "rocky": {
        "10": BuildOS(family=OSFamilyEnum.REDHAT_LIKE, name="rocky", version="10"),
        "9": BuildOS(family=OSFamilyEnum.REDHAT_LIKE, name="rocky", version="9"),
        "8": BuildOS(family=OSFamilyEnum.REDHAT_LIKE, name="rocky", version="8"),
    },
    "scratch": BuildOS(family=OSFamilyEnum.UNKNOWN, name="scratch", version=""),
    "unknown": BuildOS(family=OSFamilyEnum.UNKNOWN, name="unknown", version=""),
}

DEFAULT_OS = SUPPORTED_OS["ubuntu"]["22"]
