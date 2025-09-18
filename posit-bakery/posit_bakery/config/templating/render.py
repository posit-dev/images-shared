import re

import jinja2

from posit_bakery.const import REGEX_IMAGE_TAG_SUFFIX_ALLOWED_CHARACTERS_PATTERN
from posit_bakery.error import BakeryTemplateError


def raise_template_exception(message: str) -> None:
    """Raises a ValueError with the provided message.

    :param message: The error message to raise.

    :raises ValueError: Always raises a ValueError with the provided message.
    """
    raise BakeryTemplateError(message)


def jinja2_env(**kwargs) -> jinja2.Environment:
    """Creates a Jinja2 environment with custom filters

    :param kwargs: Additional keyword arguments to pass to the Jinja2 Environment constructor.
    :return: A Jinja2 Environment instance with custom filters added.
    """
    env = jinja2.Environment(**kwargs)
    env.filters["tagSafe"] = lambda s: re.sub(REGEX_IMAGE_TAG_SUFFIX_ALLOWED_CHARACTERS_PATTERN, "-", s).strip("-._")
    env.filters["stripMetadata"] = lambda s: re.sub(r"[+-](?=[^+-]*$).*", "", s)
    env.filters["condense"] = lambda s: re.sub(r"[ .-]", "", s)
    env.filters["regexReplace"] = lambda s, find, replace: re.sub(find, replace, s)
    env.filters["quote"] = lambda s: '"' + s + '"'
    env.filters["split"] = lambda s, sep: s.split(sep)
    env.globals["raise"] = raise_template_exception
    return env


def render_template(template: str, **kwargs) -> str:
    """Renders a Jinja2 template with the provided keyword arguments and custom filters added

    :param template: The Jinja2 template string to render.
    :param kwargs: Additional values to pass to the template for rendering.
    :return: The rendered template as a string, with leading and trailing whitespace removed.
    """
    template = jinja2_env().from_string(template)
    return template.render(**kwargs).strip()
