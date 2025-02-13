import logging
import re
from enum import Enum, EnumType
from typing import Annotated, Dict, Self, List, Union

from pydantic import BaseModel, Field, model_validator
from pydantic.functional_validators import field_validator
from pydantic_core import PydanticUseDefault

log = logging.getLogger(__name__)

REGEX_SNYK_MONITOR_TAG_KEY = re.compile(r"^[a-zA-Z0-9_-]+$")
SNYK_MONITOR_TAG_KEY_LENGTH = 30
REGEX_SNYK_MONITOR_TAG_VALUE = re.compile(r"^[a-zA-Z0-9_\-/:?#@&+=%~]+$")
SNYK_MONITOR_TAG_VALUE_LENGTH = 256


class SnykContainerSubcommand(str, Enum):
    test = "test"
    monitor = "monitor"
    sbom = "sbom"


class SnykTestOutputFormatEnum(str, Enum):
    """Enum for the supported output formats for snyk container test output."""
    sarif = "sarif"
    json = "json"
    default = "default"


class SnykSeverityThresholdEnum(str, Enum):
    """Enum for the supported severity thresholds for snyk container test/monitor."""
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


SNYK_DEFAULT_SEVERITY_THRESHOLD = SnykSeverityThresholdEnum.medium


class SnykBusinessCriticalityEnum(str, Enum):
    """Enum for the supported business criticality values for snyk container monitor."""
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class SnykEnvironmentEnum(str, Enum):
    """Enum for the supported environment values for snyk container monitor."""
    frontend = "frontend"
    backend = "backend"
    internal = "internal"
    external = "external"
    mobile = "mobile"
    saas = "saas"
    onprem = "onprem"
    hosted = "hosted"
    distributed = "distributed"


class SnykLifecycleEnum(str, Enum):
    """Enum for the supported lifecycle values for snyk container monitor."""
    development = "development"
    sandbox = "sandbox"
    production = "production"


class SnykSbomFormatEnum(str, Enum):
    """Enum for the supported SBOM formats for snyk container sbom."""
    cyclonedx1_4_json = "cyclonedx1.4+json"
    cyclonedx1_5_json = "cyclonedx1.5+json"
    cyclonedx1_6_json = "cyclonedx1.6+json"
    cyclonedx1_4_xml = "cyclonedx1.4+xml"
    cyclonedx1_5_xml = "cyclonedx1.5+xml"
    cyclonedx1_6_xml = "cyclonedx1.6+xml"
    spdx2_3_json = "spdx2.3+json"


SNYK_DEFAULT_SBOM_FORMAT = SnykSbomFormatEnum.cyclonedx1_5_json


def clean(value: List[str] | str) -> List[str]:
    """Clean a list of strings or a single string

    :param value: The value to clean
    :return: The cleaned value as a list of strings
    """
    if isinstance(value, list):
        return [v.strip() for v in value if v.strip()]
    return [v.strip() for v in value.split(",") if v.strip()]


def validate_list(
        values: List[str], message: str, validator: re.Pattern | EnumType = None
) -> Union[List[str], str]:
    """Validate a list of strings against a regex pattern or EnumType

    :param values: The values to validate as a list of strings
    :param message: The warning message to log if the value is invalid
    :param validator: The regex pattern or enum to validate the value against
    :return: The validated value as a list of strings or a single string
    """
    if not isinstance(validator, EnumType) and not isinstance(validator, re.Pattern):
        raise ValueError("Validator must be an EnumType or re.Pattern object.")

    def validate(_value: str) -> EnumType | str | None:
        """Validates a single string against a regex pattern or EnumType

        :param _value: The string to validate
        :return: The validated string or None if invalid
        """
        if isinstance(validator, EnumType):
            try:
                _value = validator[_value.lower()]
            except KeyError:
                return None
        elif isinstance(validator, re.Pattern):
            match = validator.match(_value)
            if match is None:
                return None
        else:
            return None
        return _value

    return_values = []
    for value in values:
        validated_value = validate(value)
        if validated_value is None:
            log.warning(message % value)
        else:
            return_values.append(validated_value)
    if len(return_values) > 0:
        return return_values

    raise PydanticUseDefault()


class ManifestSnykTestOutput(BaseModel):
    format: SnykTestOutputFormatEnum = SnykTestOutputFormatEnum.default
    json_file: bool = False
    sarif_file: bool = False

    @field_validator("format", mode="wrap")
    @classmethod
    def validate_format_to_warning(cls, value, handler):
        try:
            return handler(value)
        except ValueError:
            log.warning(
                f"Invalid value for snyk.test.output.format, expected '{value}' to be one of "
                f"{", ".join([e.value for e in SnykTestOutputFormatEnum])}. Using default value "
                f"'{SnykTestOutputFormatEnum.default.value}'."
            )
            raise PydanticUseDefault()


class ManifestSnykTest(BaseModel):
    severity_threshold: SnykSeverityThresholdEnum = SNYK_DEFAULT_SEVERITY_THRESHOLD
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
                f"Invalid value for snyk.test.severity_threshold, expected '{value}' to be one of "
                f"{", ".join([e.value for e in SnykSeverityThresholdEnum])}. Using default value "
                f"'{SNYK_DEFAULT_SEVERITY_THRESHOLD}'."
            )
            raise PydanticUseDefault()


class ManifestSnykMonitor(BaseModel):
    include_app_vulns: bool = True
    include_node_modules: bool = True
    output_json: bool = False
    environment: List[SnykEnvironmentEnum] | None = None
    lifecycle: List[SnykLifecycleEnum] | None = None
    business_criticality: List[SnykBusinessCriticalityEnum] | None = None
    tags: Dict[str, str] | None = None

    @field_validator("environment", mode="before")
    @classmethod
    def validate_environment_to_warning(cls, value: Union[List[str], str, None]) -> Union[List[str], str, None]:
        warn_message = (
            "Invalid value for snyk.monitor.environment, expected '%s' to be one of "
            f"{", ".join([e.value for e in SnykEnvironmentEnum])}. Environment will not be "
            "passed to Snyk."
        )

        if value is None:
            raise PydanticUseDefault()
        elif value == "":
            log.warning("Invalid value for snyk.monitor.environment, expected a non-empty string or list of strings.")
            raise PydanticUseDefault()

        values_as_list = clean(value)

        return validate_list(values_as_list, warn_message, validator=SnykEnvironmentEnum)

    @field_validator("lifecycle", mode="before")
    @classmethod
    def validate_lifecycle_to_warning(cls, value: Union[List[str], str, None]) -> Union[List[str], str, None]:
        warn_message = (
            "Invalid value for snyk.monitor.lifecycle, expected '%s' to match regex pattern "
            f"{", ".join([e.value for e in SnykLifecycleEnum])}. Lifecycle will not be passed to Snyk."
        )

        if value is None:
            raise PydanticUseDefault()
        elif value == "":
            log.warning("Invalid value for snyk.monitor.lifecycle, expected a non-empty string or list of strings.")
            raise PydanticUseDefault()

        values_as_list = clean(value)

        return validate_list(values_as_list, warn_message, validator=SnykLifecycleEnum)

    @field_validator("business_criticality", mode="before")
    @classmethod
    def validate_business_criticality_to_warning(
            cls, value: Union[List[str], str, None]
    ) -> Union[List[str], str, None]:
        warn_message = (
            "Invalid value for snyk.monitor.business_criticality, expected '%s' to match regex pattern "
            f"{", ".join([e.value for e in SnykBusinessCriticalityEnum])}. Business criticality will not be "
            "passed to Snyk."
        )

        if value is None:
            raise PydanticUseDefault()
        elif value == "":
            log.warning(
                "Invalid value for snyk.monitor.business_criticality, expected a non-empty string or list of strings."
            )
            raise PydanticUseDefault()

        values_as_list = clean(value)

        return validate_list(values_as_list, warn_message, validator=SnykBusinessCriticalityEnum)

    @model_validator(mode="after")
    def validate_tags(self) -> "ManifestSnykMonitor":
        if self.tags is None:
            return self

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
    format: SnykSbomFormatEnum = SNYK_DEFAULT_SBOM_FORMAT

    @field_validator("format", mode="wrap")
    @classmethod
    def validate_format_to_warning(cls, value, handler):
        try:
            return handler(value)
        except ValueError:
            log.warning(
                f"Invalid value for snyk.sbom.format, expected '{value}' to be one of "
                f"'{", ".join([e.value for e in SnykSbomFormatEnum])}'. Using default value "
                f"'{SNYK_DEFAULT_SBOM_FORMAT}'."
            )
            raise PydanticUseDefault()


class ManifestSnyk(BaseModel):
    test: Annotated[ManifestSnykTest, Field(default_factory=ManifestSnykTest)]
    monitor: Annotated[ManifestSnykMonitor, Field(default_factory=ManifestSnykMonitor)]
    sbom: Annotated[ManifestSnykSbom, Field(default_factory=ManifestSnykSbom)]
