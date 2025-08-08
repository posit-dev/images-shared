import re

import jinja2


def jinja2_env(**kwargs) -> jinja2.Environment:
    """Creates a Jinja2 environment with custom filters

    :param kwargs: Additional keyword arguments to pass to the Jinja2 Environment constructor.
    :return: A Jinja2 Environment instance with custom filters added.
    """
    env = jinja2.Environment(**kwargs)
    env.filters["tagSafe"] = lambda s: re.sub(r"[^a-zA-Z0-9_\-.]", "-", s)
    env.filters["stripMetadata"] = lambda s: re.sub(r"[+-](?=[^+-]*$).*", "", s)
    env.filters["condense"] = lambda s: re.sub(r"[ .-]", "", s).lower()
    env.filters["regexReplace"] = lambda s, find, replace: re.sub(find, replace, s)
    return env


def render_template(template: str, **kwargs) -> str:
    """Renders a Jinja2 template with the provided keyword arguments and custom filters added

    :param template: The Jinja2 template string to render.
    :param kwargs: Additional values to pass to the template for rendering.
    :return: The rendered template as a string, with leading and trailing whitespace removed.
    """
    template = jinja2_env().from_string(template)
    return template.render(**kwargs).strip()
