"""Settings and filter models for Bakery target selection.

Extracted from config.py to reduce coupling to the execution layer.
"""

import logging
import warnings
from typing import Annotated, Any

from pydantic import BaseModel, Field, model_validator

from posit_bakery.config.image.dev_version.spec import DevBuildSpec
from posit_bakery.config.image.posit_product.const import ReleaseChannelEnum
from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum

log = logging.getLogger(__name__)


class BakeryConfigFilter(BaseModel):
    """Container for filtering options when generating image targets from the BakeryConfig."""

    image_name: Annotated[
        str | None, Field(description="Name or regex pattern of the image to filter by.", default=None)
    ]
    image_variant: Annotated[
        str | None, Field(description="Name or regex pattern of the image variant to filter by.", default=None)
    ]
    image_version: Annotated[str | None, Field(description="Version string or prefix to filter by.", default=None)]
    image_os: Annotated[
        str | None, Field(description="Name or regex pattern of the image OS to filter by.", default=None)
    ]
    image_platform: Annotated[
        list[str], Field(description="Name or regex pattern of the image platform to filter by.", default_factory=list)
    ]


class BakerySettings(BaseModel):
    """Container for global settings that can be applied to the BakeryConfig."""

    filter: BakeryConfigFilter = Field(
        default_factory=BakeryConfigFilter, description="Filter(s) to apply when generating image targets."
    )
    dev_versions: Annotated[
        DevVersionInclusionEnum,
        Field(
            description="Include or exclude development versions defined in config.",
            default=DevVersionInclusionEnum.EXCLUDE,
        ),
    ]
    dev_channel: Annotated[
        ReleaseChannelEnum | None,
        Field(
            default=None,
            description="Filter development versions to a specific release channel.",
        ),
    ] = None
    dev_spec: Annotated[
        DevBuildSpec | None,
        Field(
            default=None,
            description="Pinned dev build spec from a workflow dispatch. When set, overrides "
            "CDN discovery for the matching channel dev version.",
        ),
    ] = None

    @model_validator(mode="before")
    @classmethod
    def migrate_dev_stream_to_dev_channel(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "dev_stream" in data and data.get("dev_channel") is None:
            warnings.warn(
                "BakerySettings: 'dev_stream' is deprecated, use 'dev_channel' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            data = dict(data)
            data["dev_channel"] = data.pop("dev_stream")
        elif "dev_stream" in data:
            # dev_channel already set — dev_channel wins, drop the stale dev_stream key
            data = dict(data)
            data.pop("dev_stream")
        return data

    @property
    def dev_stream(self) -> ReleaseChannelEnum | None:
        """Deprecated: use dev_channel."""
        warnings.warn(
            "BakerySettings.dev_stream is deprecated, use dev_channel instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.dev_channel

    @property
    def effective_dev_channel(self) -> ReleaseChannelEnum | None:
        """Channel used to filter dev versions, honoring both --dev-channel and --dev-spec.

        A --dev-spec carrying a channel implies dev versions should be filtered to
        that channel. The shared CI workflow folds the dispatched channel into the
        dev-spec and stops passing --dev-channel, so without this derivation the
        other channels' dev versions leak through both the matrix output and the
        build target list. --dev-channel wins when explicitly set; _apply_dev_spec
        validates that the two never conflict.
        """
        if self.dev_channel is not None:
            return self.dev_channel
        if self.dev_spec is not None:
            return self.dev_spec.channel
        return None

    matrix_versions: Annotated[
        MatrixVersionInclusionEnum,
        Field(
            description="Include or exclude versions defined in image matrix.",
            default=MatrixVersionInclusionEnum.EXCLUDE,
        ),
    ]
    latest: Annotated[
        bool,
        Field(
            description="Build only the latest version of each image. Development versions are ignored.",
            default=False,
        ),
    ]
    recent: Annotated[
        int | None,
        Field(
            default=None,
            gt=0,
            description="Limit non-matrix images to their N highest-sorted release versions.",
        ),
    ]
    clean_temporary: Annotated[
        bool, Field(description="Clean intermediary and temporary files created by Bakery.", default=True)
    ]
    cache_registry: Annotated[str | None, Field(description="Registry to use for image build cache.", default=None)]
    temp_registry: Annotated[str | None, Field(description="Registry to use for image build temp cache.", default=None)]
