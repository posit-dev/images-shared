import re

import jinja2


def tag_safe(s: str) -> str:
    """Replaces '+' with '-' in a string to make it safe for use in a tag"""
    return s.replace("+", "-")


def clean_version(s: str) -> str:
    """Cleans a version string by removing any trailing metadata"""
    return re.sub(r"[+|-].*", "", s)


def condense(s: str) -> str:
    """Condenses a string by removing spaces, dashes, and periods and converting to lowercase"""
    return s.replace(" ", "").replace("-", "").replace(".", "").lower()


def regex_replace(s: str, find: str, replace: str) -> str:
    """Jinja2 filter to replace a regex pattern in a string."""
    return re.sub(find, replace, s)


def jinja2_env(**kwargs) -> jinja2.Environment:
    """Creates a Jinja2 environment with custom filters"""
    env = jinja2.Environment(**kwargs)
    env.filters["tag_safe"] = tag_safe
    env.filters["clean_version"] = clean_version
    env.filters["condense"] = condense
    env.filters["regex_replace"] = regex_replace
    return env


def render_template(template: str, **kwargs) -> str:
    """Renders a Jinja2 template with the provided keyword arguments and custom filters added"""
    template = jinja2_env().from_string(template)
    return template.render(**kwargs).strip()
