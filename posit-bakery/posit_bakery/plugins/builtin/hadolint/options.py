from copy import deepcopy
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from posit_bakery.config.tools.base import ToolOptions

# Package-pinning rules ignored by default since Posit images do not pin
# OS-level package versions. Users can override by setting `ignored` explicitly;
# setting `ignored: []` clears the defaults entirely.
DEFAULT_IGNORED_RULES: list[str] = ["DL3008", "DL3018", "DL3033", "DL3037", "DL3041"]


class HadolintOverride(BaseModel):
    """Override the default severity level of specific hadolint rules."""

    error: Annotated[
        list[str] | None,
        Field(default=None, description="List of rule codes to treat as errors."),
    ]
    warning: Annotated[
        list[str] | None,
        Field(default=None, description="List of rule codes to treat as warnings."),
    ]
    info: Annotated[
        list[str] | None,
        Field(default=None, description="List of rule codes to treat as info."),
    ]
    style: Annotated[
        list[str] | None,
        Field(default=None, description="List of rule codes to treat as style."),
    ]


class HadolintOptions(ToolOptions):
    """Configuration options for hadolint Containerfile linting."""

    tool: Literal["hadolint"] = "hadolint"
    failureThreshold: Annotated[
        str | None,
        Field(
            default=None,
            description="Exit with failure status if any rule at or above this severity is violated. "
            "One of: error, warning, info, style, ignore, none.",
        ),
    ]
    ignored: Annotated[
        list[str] | None,
        Field(default=None, description="List of hadolint rule codes to ignore (e.g. DL3008, SC2086)."),
    ]
    labelSchema: Annotated[
        dict[str, str] | None,
        Field(
            default=None,
            description="Label validation schema mapping label names to expected value formats "
            "(text, rfc3339, semver, url, hash, spdx, email).",
        ),
    ]
    noFail: Annotated[
        bool | None,
        Field(default=None, description="Always exit with status 0, even when rule violations are found."),
    ]
    override: Annotated[
        HadolintOverride | None,
        Field(default=None, description="Override the default severity level of specific rules."),
    ]
    strictLabels: Annotated[
        bool | None,
        Field(
            default=None,
            description="Require labels to match the label schema. Only labels set directly in the Containerfile "
            "can be validated, since hadolint operates on the static Containerfile definition.",
        ),
    ]
    disableIgnorePragma: Annotated[
        bool | None,
        Field(
            default=None,
            description="Disable inline hadolint ignore comments (e.g. '# hadolint ignore=DL3008').",
        ),
    ]
    trustedRegistries: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="List of trusted Docker registries. Images from untrusted registries trigger DL3026.",
        ),
    ]

    def update(self, other: "HadolintOptions") -> "HadolintOptions":
        """Update this HadolintOptions with settings from another.

        The merge strategy uses the other instance's values where the current
        instance has None (not explicitly set).
        """
        merged = deepcopy(self)
        for field_name in HadolintOptions.model_fields:
            if field_name == "tool":
                continue
            if getattr(self, field_name) is None and field_name not in self.model_fields_set:
                other_value = getattr(other, field_name)
                if other_value is not None:
                    setattr(merged, field_name, deepcopy(other_value))
        return merged
