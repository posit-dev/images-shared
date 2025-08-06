import re

import jinja2


def jinja2_env(**kwargs) -> jinja2.Environment:
    """Creates a Jinja2 environment with custom filters"""
    env = jinja2.Environment(**kwargs)
    env.filters["tagSafe"] = lambda s: re.sub(r"[^a-zA-Z0-9_\-.]", "-", s)
    env.filters["stripMetadata"] = lambda s: re.sub(r"[+|-].*", "", s)
    env.filters["condense"] = lambda s: re.sub(r"[ .-]", "", s)
    env.filters["regexReplace"] = lambda s, find, replace: re.sub(find, replace, s)
    return env


def render_template(template: str, **kwargs) -> str:
    """Renders a Jinja2 template with the provided keyword arguments and custom filters added"""
    template = jinja2_env().from_string(template)
    return template.render(**kwargs).strip()
