import logging
import re
from typing import Annotated, Dict

from pydantic import BaseModel, Field, model_validator

REGEX_SNYK_TEST_SEVERITY_THRESHOLD = re.compile(r"^(low|medium|high|critical)$")

REGEX_SNYK_MONITOR_PROJECT_ENVIRONMENT = re.compile(r"^(frontend|backend|internal|external|mobile|saas|onprem|hosted|distributed)$")
REGEX_SNYK_MONITOR_PROJECT_LIFECYCLE = re.compile(r"^(development|sandbox|production)$")
REGEX_SNYK_MONITOR_PROJECT_BUSINESS_CRITICALITY = re.compile(r"^(low|medium|high|critical)$")
REGEX_SNYK_MONITOR_TAG_KEY = re.compile(r"^[a-zA-Z0-9_-]+$")
SNYK_MONITOR_TAG_KEY_LENGTH = 30
REGEX_SNYK_MONITOR_TAG_VALUE = re.compile(r"^[a-zA-Z0-9_\-/:?#@&+=%~]+$")
SNYK_MONITOR_TAG_VALUE_LENGTH = 256

REGEX_SNYK_SBOM_FORMAT = re.compile(r"^(cyclonedx1\.[45]\+(json|xml)|spdx2\.3\+json)$")


log = logging.getLogger("rich")


class ManifestSnykTestOutput(BaseModel):
    json: bool = False
    json_file: bool = False
    sarif: bool = False
    sarif_file: bool = False


class ManifestSnykTest(BaseModel):
    severity_threshold: Annotated[str, Field(pattern=REGEX_SNYK_TEST_SEVERITY_THRESHOLD)] = "medium"
    include_app_vulns: bool = True
    include_base_image_vulns: bool = False
    output: Annotated[ManifestSnykTestOutput, Field(default_factory=ManifestSnykTestOutput)]


class ManifestSnykMonitor(BaseModel):
    include_app_vulns: bool = True
    output_json: bool = False
    environment: Annotated[str | None, Field(pattern=REGEX_SNYK_MONITOR_PROJECT_ENVIRONMENT)] = None
    lifecycle: Annotated[str | None, Field(pattern=REGEX_SNYK_MONITOR_PROJECT_LIFECYCLE)] = None
    business_criticality: Annotated[str | None, Field(pattern=REGEX_SNYK_MONITOR_PROJECT_BUSINESS_CRITICALITY)] = None
    tags: Dict[str, str] | None = None

    @model_validator(mode="after")
    def validate_tags(self) -> Dict[str, str] | None:
        if self.tags is None:
            return None

        for key, value in self.tags.items():
            if len(key) > SNYK_MONITOR_TAG_KEY_LENGTH:
                log.warning(f"Snyk tag key '{key}' exceeds limit of {SNYK_MONITOR_TAG_KEY_LENGTH} characters.")
            if len(value) > SNYK_MONITOR_TAG_VALUE_LENGTH:
                log.warning(f"Snyk tag value '{value}' exceeds limit of {SNYK_MONITOR_TAG_VALUE_LENGTH} characters.")
            if not REGEX_SNYK_MONITOR_TAG_KEY.match(key):
                log.warning(
                    f"Snyk tag key '{key}' does not match regex pattern. Keys must be alphanumeric and may use '-' and "
                    f"'_'."
                )
            if not REGEX_SNYK_MONITOR_TAG_VALUE.match(value):
                log.warning(
                    f"Snyk tag value '{value}' does not match regex pattern. Values must be alphanumeric and may use "
                    f"'-', '_', ':', '?', '@', '&', '+', '=', '~', and '%'."
                )

        return self


class ManifestSnykSbom(BaseModel):
    include_app_vulns: bool = True
    format: Annotated[str, Field(pattern=REGEX_SNYK_SBOM_FORMAT)] = "cyclonedx1.5+json"


class ManifestSnyk(BaseModel):
    test: Annotated[ManifestSnykTest, Field(default_factory=ManifestSnykTest)]
    monitor: Annotated[ManifestSnykMonitor, Field(default_factory=ManifestSnykMonitor)]
    sbom: Annotated[ManifestSnykSbom, Field(default_factory=ManifestSnykSbom)]
