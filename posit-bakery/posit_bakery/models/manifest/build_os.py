class BuildOS:
    distributor_id: str
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

    :param distributor_id: Distributor ID field from lsb_release
    :param name: NAME field from os-release
    :param version: Major version of the OS
    :param base: Base container image
    :param tag: Container image tag
    :param codename: VERSION_CODENAME from os-release
    """

    def __init__(
        self,
        distributor_id: str,
        name: str,
        version: str,
        base_image: str,
        image_tag: str,
        codename: str = None,
    ):
        self.distributor_id = distributor_id
        self.name = name
        self.version = version
        self.base_image = base_image
        self.image_tag = image_tag
        self.codename = codename
        self.pretty = f"{name} {version}"
