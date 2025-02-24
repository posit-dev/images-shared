from pathlib import Path
from typing import Dict, List, Annotated

from pydantic import BaseModel, Field
from posit_bakery.models.manifest.goss import ManifestGoss


class ImageLabels(BaseModel):
    posit: Dict[str, str] = {}
    oci: Dict[str, str] = {}
    posit_prefix: str = "co.posit.image"
    oci_prefix: str = "org.opencontainers.image"


class ImageMetadata(BaseModel):
    name: str
    version: str | None = None
    context: Path | None = None
    labels: Annotated[ImageLabels, Field(default_factory=ImageLabels)]
    tags: List[str] = []
    goss: Annotated[ManifestGoss, Field(default_factory=ManifestGoss)]
