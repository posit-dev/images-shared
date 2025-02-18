import re
from pathlib import Path
from typing import List

from posit_bakery.models.manifest.build_os import BuildOS
from posit_bakery.templating.filters import condense


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
    BuildOS(
        distributor_id="scratch",
        name="scratch",
        version="",
        base_image="scratch",
        image_tag="scratch",
    ),
]


def find_os(identifier: str) -> BuildOS | None:
    """Find an OS object based on an identifier

    :param identifier: Pretty or Condensed name of the OS
    """
    for _os in SUPPORTED_OS:
        if identifier in [_os.pretty, _os.condensed]:
            return _os

    return None


def guess_os_list(context: Path) -> List[BuildOS]:
    """Guess the operating systems for an image based on the Containerfile extensions present in the image directory

    :param context: Path to the versioned image directory containing Containerfiles to guess OSes from
    """
    pat = re.compile(r"Containerfile\.(?P<os>[a-zA-Z]+)(?P<version>[0-9.]+)\.[a-zA-Z0-9]")
    containerfiles: List[str] = list(context.glob(f"Containerfile*"))
    containerfiles = [str(containerfile.relative_to(context)) for containerfile in containerfiles]

    os_list: List[BuildOS] = []
    for containerfile in containerfiles:
        match = pat.match(containerfile)
        if match:
            _os = find_os(condense(f"{match.group('os')} {match.group('version')}"))
            if _os and _os not in os_list:
                os_list.append(_os)

    return os_list
