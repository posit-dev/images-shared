import re

import jinja2


def tag_safe(s: str):
    return s.replace("+", "-")


def clean_version(s: str):
    return re.sub(r"[+|-].*", "", s)


def condense(s: str):
    return s.replace(" ", "").replace("-", "").replace(".", "").lower()


def jinja2_env():
    env = jinja2.Environment()
    env.filters["tag_safe"] = tag_safe
    env.filters["clean_version"] = clean_version
    env.filters["condense"] = condense
    return env


def render_template(template: str, **kwargs):
    template = jinja2_env().from_string(template)
    return template.render(**kwargs)
