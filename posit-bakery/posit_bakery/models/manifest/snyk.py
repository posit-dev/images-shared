import logging
import re
from typing import Annotated, Dict, Self

from pydantic import BaseModel, Field, model_validator
from pydantic.functional_validators import field_validator
from pydantic_core import PydanticUseDefault

REGEX_SNYK_TEST_OUTPUT_FORMAT = re.compile(r"^(sarif|json|default)$")
DEFAULT_SNYK_TEST_OUTPUT_FORMAT = "default"

REGEX_SNYK_TEST_SEVERITY_THRESHOLD = re.compile(r"^(low|medium|high|critical)$")
DEFAULT_SNYK_TEST_SEVERITY_THRESHOLD = "medium"

REGEX_SNYK_MONITOR_PROJECT_ENVIRONMENT = re.compile(r"^(frontend|backend|internal|external|mobile|saas|onprem|hosted|distributed)$")
REGEX_SNYK_MONITOR_PROJECT_LIFECYCLE = re.compile(r"^(development|sandbox|production)$")
REGEX_SNYK_MONITOR_PROJECT_BUSINESS_CRITICALITY = re.compile(r"^(low|medium|high|critical)$")
REGEX_SNYK_MONITOR_TAG_KEY = re.compile(r"^[a-zA-Z0-9_-]+$")
SNYK_MONITOR_TAG_KEY_LENGTH = 30
REGEX_SNYK_MONITOR_TAG_VALUE = re.compile(r"^[a-zA-Z0-9_\-/:?#@&+=%~]+$")
SNYK_MONITOR_TAG_VALUE_LENGTH = 256

REGEX_SNYK_SBOM_FORMAT = re.compile(r"^(cyclonedx1\.[45]\+(json|xml)|spdx2\.3\+json)$")
DEFAULT_SNYK_SBOM_FORMAT = "cyclonedx1.5+json"


log = logging.getLogger("rich")


class ManifestSnykTestOutput(BaseModel):
    format: Annotated[str, Field(pattern=REGEX_SNYK_TEST_OUTPUT_FORMAT)] = DEFAULT_SNYK_TEST_OUTPUT_FORMAT
    json_file: bool = False
    sarif_file: bool = False

    @field_validator("format", mode="wrap")
    @classmethod
    def validate_format_to_warning(cls, value, handler):
        try:
            return handler(value)
        except ValueError:
            log.warning(
                f"Invalid value for snyk.test.output.format, expected '{value}' to match regex pattern "
                f"'{REGEX_SNYK_TEST_OUTPUT_FORMAT.pattern}'. Using default value "
                f"'{DEFAULT_SNYK_TEST_OUTPUT_FORMAT}'."
            )
            raise PydanticUseDefault()


class ManifestSnykTest(BaseModel):
    severity_threshold: Annotated[str, Field(pattern=REGEX_SNYK_TEST_SEVERITY_THRESHOLD)] = DEFAULT_SNYK_TEST_SEVERITY_THRESHOLD
    include_app_vulns: bool = True
    include_base_image_vulns: bool = False
    output: Annotated[ManifestSnykTestOutput, Field(default_factory=ManifestSnykTestOutput)]

    @field_validator("severity_threshold", mode="wrap")
    @classmethod
    def validate_severity_threshold_to_warning(cls, value, handler):
        try:
            return handler(value)
        except ValueError:
            log.warning(
                f"Invalid value for snyk.test.severity_threshold, expected '{value}' to match regex pattern "
                f"'{REGEX_SNYK_TEST_SEVERITY_THRESHOLD.pattern}'. Using default value "
                f"'{DEFAULT_SNYK_TEST_SEVERITY_THRESHOLD}'."
            )
            raise PydanticUseDefault()


class ManifestSnykMonitor(BaseModel):
    include_app_vulns: bool = True
    output_json: bool = False
    environment: Annotated[str | None, Field(pattern=REGEX_SNYK_MONITOR_PROJECT_ENVIRONMENT)] = None
    lifecycle: Annotated[str | None, Field(pattern=REGEX_SNYK_MONITOR_PROJECT_LIFECYCLE)] = None
    business_criticality: Annotated[str | None, Field(pattern=REGEX_SNYK_MONITOR_PROJECT_BUSINESS_CRITICALITY)] = None
    tags: Dict[str, str] | None = None

    @field_validator("environment", mode="wrap")
    @classmethod
    def validate_environment_to_warning(cls, value, handler):
        try:
            return handler(value)
        except ValueError:
            log.warning(
                f"Invalid value for snyk.monitor.environment, expected '{value}' to match regex pattern "
                f"'{REGEX_SNYK_MONITOR_PROJECT_ENVIRONMENT.pattern}'. Environment will not be passed to Snyk."
            )
            raise PydanticUseDefault()

    @field_validator("lifecycle", mode="wrap")
    @classmethod
    def validate_lifecycle_to_warning(cls, value, handler):
        try:
            return handler(value)
        except ValueError:
            log.warning(
                f"Invalid value for snyk.monitor.lifecycle, expected '{value}' to match regex pattern "
                f"'{REGEX_SNYK_MONITOR_PROJECT_LIFECYCLE.pattern}'. Lifecycle will not be passed to Snyk."
            )
            raise PydanticUseDefault()

    @field_validator("business_criticality", mode="wrap")
    @classmethod
    def validate_business_criticality_to_warning(cls, value, handler):
        try:
            return handler(value)
        except ValueError:
            log.warning(
                f"Invalid value for snyk.monitor.business_criticality, expected '{value}' to match regex pattern "
                f"'{REGEX_SNYK_MONITOR_PROJECT_BUSINESS_CRITICALITY.pattern}'. Business criticality will not be "
                f"passed to Snyk."
            )
            raise PydanticUseDefault()

    @model_validator(mode="after")
    def validate_tags(self) -> Self:
        if self.tags is None:
            return None

        for key, value in self.tags.items():
            if len(key) > SNYK_MONITOR_TAG_KEY_LENGTH:
                log.warning(f"Snyk tag key '{key}' exceeds limit of {SNYK_MONITOR_TAG_KEY_LENGTH} characters.")
            if len(value) > SNYK_MONITOR_TAG_VALUE_LENGTH:
                log.warning(f"Snyk tag value '{value}' exceeds limit of {SNYK_MONITOR_TAG_VALUE_LENGTH} characters.")
            if not REGEX_SNYK_MONITOR_TAG_KEY.match(key):
                log.warning(
                    f"snyk.monitor.tags key '{key}' does not match regex pattern. Keys must be alphanumeric and may "
                    f"use '-' and '_'."
                )
            if not REGEX_SNYK_MONITOR_TAG_VALUE.match(value):
                log.warning(
                    f"snyk.monitor.tags.{key} value '{value}' does not match regex pattern. Values must be "
                    f"alphanumeric and may use '-', '_', ':', '?', '@', '&', '+', '=', '~', and '%'."
                )

        return self


class ManifestSnykSbom(BaseModel):
    include_app_vulns: bool = True
    format: Annotated[str, Field(pattern=REGEX_SNYK_SBOM_FORMAT)] = DEFAULT_SNYK_SBOM_FORMAT

    @field_validator("format", mode="wrap")
    @classmethod
    def validate_format_to_warning(cls, value, handler):
        try:
            return handler(value)
        except ValueError:
            log.warning(
                f"Invalid value for snyk.sbom.format, expected '{value}' to match regex pattern "
                f"'{REGEX_SNYK_SBOM_FORMAT.pattern}'. Using default value '{DEFAULT_SNYK_SBOM_FORMAT}'."
            )
            raise PydanticUseDefault()


class ManifestSnyk(BaseModel):
    test: Annotated[ManifestSnykTest, Field(default_factory=ManifestSnykTest)]
    monitor: Annotated[ManifestSnykMonitor, Field(default_factory=ManifestSnykMonitor)]
    sbom: Annotated[ManifestSnykSbom, Field(default_factory=ManifestSnykSbom)]
