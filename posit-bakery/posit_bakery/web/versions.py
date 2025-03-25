from enum import Enum


class ProductEnum(str, Enum):
    CONNECT = "connect"
    PACKAGE_MANAGER = "package-manager"
    WORKBENCH = "workbench"


class ReleaseStreamEnum(str, Enum):
    RELEASE = "release"
    PREVIEW = "preview"
    DAILY = "daily"


PRODUCT_RELEASE_STREAM_SUPPORT_MAP = {
    ProductEnum.CONNECT: [ReleaseStreamEnum.RELEASE, ReleaseStreamEnum.DAILY],
    ProductEnum.PACKAGE_MANAGER: [ReleaseStreamEnum.RELEASE, ReleaseStreamEnum.PREVIEW, ReleaseStreamEnum.DAILY],
    ProductEnum.WORKBENCH: [ReleaseStreamEnum.RELEASE, ReleaseStreamEnum.PREVIEW, ReleaseStreamEnum.DAILY],
}

PRODUCT_RELEASE_STREAM_URL_MAP = {
    ProductEnum.CONNECT: {
        ReleaseStreamEnum.RELEASE: "https://posit.co/wp-content/uploads/downloads.json",
        ReleaseStreamEnum.DAILY: "https://cdn.posit.co/connect/latest-packages.json",
    },
    ProductEnum.PACKAGE_MANAGER: {
        ReleaseStreamEnum.RELEASE: "https://posit.co/wp-content/uploads/downloads.json",
        ReleaseStreamEnum.PREVIEW: "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm-rc-latest.txt",
        ReleaseStreamEnum.DAILY: "https://cdn.posit.co/package-manager/deb/amd64/rstudio-pm-main-latest.txt",
    },
    ProductEnum.WORKBENCH: {
        ReleaseStreamEnum.RELEASE: "https://posit.co/wp-content/uploads/downloads.json",
        ReleaseStreamEnum.PREVIEW: "https://www.rstudio.com/products/rstudio/download/preview/",
        ReleaseStreamEnum.DAILY: "https://dailies.posit.co/rstudio/latest/index.json",
    },
}


class VersionArtifact:
    def __init__(self, os_codename: str, product_stream: ProductEnum, release_stream: ReleaseStreamEnum):
        self.os_codename = os_codename
        self.product_stream = product_stream
        self.release_stream = release_stream
