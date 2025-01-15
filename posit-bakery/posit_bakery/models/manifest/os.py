from typing import List


class BuildOS:
    id: str
    name: str
    version: str
    codename: str | None
    base_image: str
    image_tag: str
    pretty: str

    """
    Represent the operating systems that are supported for image builds

    Due to inconsistency in the way versions are represented in the os-release
    file, we have chosen to blend fields from os-release and lsb_release

    :param id: ID field from os-release
    :param name: NAME field from os-release
    :param version: Major version of the OS
    :param base: Base container image
    :param tag: Container image tag
    :param codename: VERSION_CODENAME from os-release
    """
    # TODO: Replace id with Distributor ID from lsb_release, which is more consistent

    def __init__(
        self,
        id: str,
        name: str,
        version: str,
        base_image: str,
        image_tag: str,
        codename: str = None,
    ):
        self.id = id
        self.name = name
        self.version = version
        self.base_image = base_image
        self.image_tag = image_tag
        self.codename = codename
        self.pretty = f"{name} {version}"


# TODO: Move to a file
SUPPORTED_OS: List[BuildOS] = [
    BuildOS(
        id="ubuntu",
        name="Ubuntu",
        version="22.04",
        codename="jammy",
        base_image="ubuntu:22.04",
        image_tag="ubuntu-22.04",
    ),
    BuildOS(
        id="ubuntu",
        name="Ubuntu",
        version="24.04",
        codename="noble",
        base_image="ubuntu:24.04",
        image_tag="ubuntu-24.04",
    ),
    BuildOS(
        id="rocky",
        name="Rocky Linux",
        version="9",
        base_image="rockylinux/rockylinux:9",
        image_tag="rockylinux-9",
    ),
]


def find_os(pretty: str) -> BuildOS | None:
    """Find an OS object based on the pretty name

    :param pretty: Pretty name of the OS
    """
    for _os in SUPPORTED_OS:
        if _os.pretty == pretty:
            return _os

    return None
