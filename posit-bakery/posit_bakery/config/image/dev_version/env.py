import os
from typing import Literal, Annotated

from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from posit_bakery.config.image.dev_version.base import BaseImageDevelopmentVersion
from posit_bakery.config.templating import jinja2_env


def _get_value_from_env(field_name: str, env_var: str) -> str | None:
    """Retrieve a value from the environment variable.

    :param field_name: The name of the field the env var is from.
    :param env_var: The environment variable to set.
    :return: The value of the environment variable, or None if not set.
    """
    if env_var is None:
        raise ValueError(f"{field_name} must be set.")

    value = os.getenv(env_var)
    if value is None:
        raise ValueError(f"Environment variable '{env_var}' is not set.")

    return value


class ImageDevelopmentVersionFromEnv(BaseImageDevelopmentVersion):
    """Image development version sourced from environment variables."""

    sourceType: Literal["env"] = "env"
    versionEnvVar: Annotated[str, Field(description="The environment variable that contains the image version name.")]
    urlEnvVar: Annotated[str, Field(description="The environment variable that contains the image URL.")]

    @field_validator("versionEnvVar", "urlEnvVar", mode="after")
    def validate_env_vars(cls, v: str, info: ValidationInfo):
        """Validate that the environment variable names are not empty and are set in the environment.

        :param v: The environment variable.
        :param info: ValidationInfo containing the data being validated.
        :return: The environment variable with leading and trailing whitespace stripped.
        """
        v = v.strip()

        if not v:
            raise ValueError(f"{info.field_name} must be set.")

        env_value = os.getenv(v)
        if not env_value:
            raise ValueError(f"Environment variable '{v}' is not set.")

        return v

    def get_version(self) -> str:
        """Retrieve the version from the specified environment variable.

        :return: The version string from the environment variable.
        """
        return _get_value_from_env("versionEnvVar", self.versionEnvVar)

    def get_url_by_os(self) -> dict[str, str]:
        """Retrieve the URL from the specified environment variable.

        :return: The URL string from the environment variable.
        """
        url = _get_value_from_env("urlEnvVar", self.urlEnvVar)
        d = {}
        for _os in self.os:
            env = jinja2_env()
            template = env.from_string(url)
            rendered_url = template.render(
                **{
                    "OS": {
                        "name": _os.buildOS.name,
                        "version": _os.buildOS.version,
                        "family": _os.buildOS.family,
                        "codename": _os.buildOS.codename,
                    }
                }
            )
            rendered_url = rendered_url.strip()
            d[_os.name] = rendered_url

        return d
