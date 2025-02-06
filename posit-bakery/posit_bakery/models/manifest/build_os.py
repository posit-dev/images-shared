from pydantic import BaseModel, ConfigDict, computed_field

from posit_bakery.templating.filters import condense


class BuildOS(BaseModel):
    model_config = ConfigDict(frozen=True)

    distributor_id: str
    name: str
    version: str
    codename: str | None = None
    base_image: str
    image_tag: str

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

    @computed_field
    @property
    def pretty(self) -> str:
        return f"{self.name} {self.version}"

    @computed_field
    @property
    def condensed(self) -> str:
        return condense(self.pretty)
