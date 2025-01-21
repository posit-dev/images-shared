import logging
import re
from typing import Annotated, Dict, Self, List, Union

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

REGEX_SNYK_SBOM_FORMAT = re.compile(r"^(cyclonedx1\.[4-6]\+(json|xml)|spdx2\.3\+json)$")
DEFAULT_SNYK_SBOM_FORMAT = "cyclonedx1.5+json"


log = logging.getLogger("rich")


def validate_list_of_strings_or_string(value: Union[List[str], str], regex_pat: re.Pattern, message: str) -> Union[List[str], str]:
    if isinstance(value, str):
        # If value is a string containing commas, parse and validate it as a list of string input values
        if "," in value:
            split_values = value.split(",")
            return_values = []
            for split_value in split_values:
                if not regex_pat.match(split_value):
                    log.warning(message % split_value)
                else:
                    return_values.append(split_value)
            if len(return_values) > 0:
                return return_values
        # If value is a single string, validate it as a single string input value
        else:
            if regex_pat.match(value):
                return value
            else:
                log.warning(message % value)
    # If value is a list of strings, validate each string in the list and return the list of valid strings
    if isinstance(value, list):
        return_values = []
        for val in value:
            if not regex_pat.match(val):
                log.warning(message % val)
            else:
                return_values.append(val)
        if len(return_values) > 0:
            return return_values

    raise PydanticUseDefault()


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
    severity_threshold: Annotated[
        str, Field(pattern=REGEX_SNYK_TEST_SEVERITY_THRESHOLD)
    ] = DEFAULT_SNYK_TEST_SEVERITY_THRESHOLD
    include_app_vulns: bool = True
    include_base_image_vulns: bool = False
    include_node_modules: bool = True
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
    include_node_modules: bool = True
    output_json: bool = False
    environment: List[str] | str | None = None
    lifecycle: List[str] | str | None = None
    business_criticality: List[str] | str | None = None
    tags: Dict[str, str] | None = None

    @field_validator("environment", mode="before")
    @classmethod
    def validate_environment_to_warning(cls, value: Union[List[str], str, None]) -> Union[List[str], str, None]:
        warn_message = (
            "Invalid value for snyk.monitor.environment, expected '%s' to match regex "
            f"pattern '{REGEX_SNYK_MONITOR_PROJECT_ENVIRONMENT.pattern}'. Environment will not be "
            "passed to Snyk."
        )

        # If value is an empty string, use default value
        if value == "":
            log.warning("Invalid value for snyk.monitor.environment, expected a non-empty string or list of strings.")
            raise PydanticUseDefault()

        return validate_list_of_strings_or_string(value, REGEX_SNYK_MONITOR_PROJECT_ENVIRONMENT, warn_message)

    @field_validator("lifecycle", mode="before")
    @classmethod
    def validate_lifecycle_to_warning(cls, value: Union[List[str], str, None]) -> Union[List[str], str, None]:
        warn_message = (
            "Invalid value for snyk.monitor.lifecycle, expected '%s' to match regex pattern "
            f"'{REGEX_SNYK_MONITOR_PROJECT_LIFECYCLE.pattern}'. Lifecycle will not be passed to Snyk."
        )

        # If value is an empty string, use default value
        if value == "":
            log.warning("Invalid value for snyk.monitor.lifecycle, expected a non-empty string or list of strings.")
            raise PydanticUseDefault()

        return validate_list_of_strings_or_string(value, REGEX_SNYK_MONITOR_PROJECT_LIFECYCLE, warn_message)

    @field_validator("business_criticality", mode="before")
    @classmethod
    def validate_business_criticality_to_warning(
            cls, value: Union[List[str], str, None]
    ) -> Union[List[str], str, None]:
        warn_message = (
            "Invalid value for snyk.monitor.business_criticality, expected '%s' to match regex pattern "
            f"'{REGEX_SNYK_MONITOR_PROJECT_BUSINESS_CRITICALITY.pattern}'. Business criticality will not be "
            "passed to Snyk."
        )

        if value == "":
            log.warning(
                "Invalid value for snyk.monitor.business_criticality, expected a non-empty string or list of strings."
            )
            raise PydanticUseDefault()

        return validate_list_of_strings_or_string(value, REGEX_SNYK_MONITOR_PROJECT_BUSINESS_CRITICALITY, warn_message)

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
