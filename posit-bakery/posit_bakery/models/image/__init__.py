from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel
from posit_bakery.models.manifest.goss import ManifestGoss


class ImageLabels(BaseModel):
    posit: Dict[str, str] = {}
    oci: Dict[str, str] = {}
    posit_prefix: str = "co.posit.image"
    oci_prefix: str = "org.opencontainers.image"


class ImageMetadata(BaseModel):
    name: str
    version: str = None
    context: Path = None
    labels: ImageLabels = ImageLabels()
    tags: List[str] = []
    goss: ManifestGoss = ManifestGoss()
