from pydantic import BaseModel

from posit_bakery.config.shared import OSFamilyEnum


class BuildOS(BaseModel):
    family: OSFamilyEnum
    name: str
    version: str
    code_name: str | None = None

    @property
    def major_version(self) -> str:
        return self.version.split(".")[0]

    @property
    def package_suffix(self) -> str:
        if self.family == OSFamilyEnum.DEBIAN_LIKE:
            return "deb"
        elif self.family == OSFamilyEnum.REDHAT_LIKE or self.family == OSFamilyEnum.SUSE_LIKE:
            return "rpm"
        return ""

    @property
    def package_arch_sep(self) -> str:
        if self.family == OSFamilyEnum.REDHAT_LIKE or self.family == OSFamilyEnum.SUSE_LIKE:
            return "."
        return "_"

    @property
    def package_version_sep(self) -> str:
        if self.family == OSFamilyEnum.REDHAT_LIKE or self.family == OSFamilyEnum.SUSE_LIKE:
            return "-"
        return "_"


ALTERNATE_NAMES = {
    "redhat": "rhel",
    "rh": "rhel",
    "el": "rhel",
    "almalinux": "alma",
    "rockylinux": "rocky",
}


SUPPORTED_OS = {
    "ubuntu": {
        "24": BuildOS(family=OSFamilyEnum.DEBIAN_LIKE, name="ubuntu", version="24.04", code_name="noble"),
        "22": BuildOS(family=OSFamilyEnum.DEBIAN_LIKE, name="ubuntu", version="22.04", code_name="jammy"),
    },
    "debian": {
        "13": BuildOS(family=OSFamilyEnum.DEBIAN_LIKE, name="debian", version="13", code_name="trixie"),
        "12": BuildOS(family=OSFamilyEnum.DEBIAN_LIKE, name="debian", version="12", code_name="bookworm"),
        "11": BuildOS(family=OSFamilyEnum.DEBIAN_LIKE, name="debian", version="11", code_name="bullseye"),
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
}
