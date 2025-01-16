from typing import List

from posit_bakery.models.manifest.build_os import BuildOS


SUPPORTED_OS: List[BuildOS] = [
    BuildOS(
        distributor_id="Ubuntu",
        name="Ubuntu",
        version="22.04",
        codename="jammy",
        base_image="ubuntu:22.04",
        image_tag="ubuntu-22.04",
    ),
    BuildOS(
        distributor_id="Ubuntu",
        name="Ubuntu",
        version="24.04",
        codename="noble",
        base_image="ubuntu:24.04",
        image_tag="ubuntu-24.04",
    ),
    BuildOS(
        distributor_id="Rocky",
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
