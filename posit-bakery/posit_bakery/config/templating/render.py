import re

import jinja2
from packaging.version import InvalidVersion

from posit_bakery.config.dependencies.version import DependencyVersion, strip_patch
from posit_bakery.const import REGEX_IMAGE_TAG_SUFFIX_ALLOWED_CHARACTERS_PATTERN
from posit_bakery.error import BakeryTemplateError


def raise_template_exception(message: str) -> None:
    """Raises a ValueError with the provided message.

    :param message: The error message to raise.

    :raises ValueError: Always raises a ValueError with the provided message.
    """
    raise BakeryTemplateError(message)


def max_version(versions: str | list[str] | tuple[str, ...]) -> str:
    """Returns the highest version from a list or comma-separated string of versions.

    Versions are compared with ``DependencyVersion`` (semver-style, pre-releases accepted). The original string of the
    winning entry is returned. Ties go to the later entry. A single entry is returned as-is without being parsed, which
    lets placeholders such as ``${PYTHON_VERSION}`` pass through.

    :param versions: A list of version strings or a comma-separated string of versions.

    :raises BakeryTemplateError: If the input is empty or contains an entry that is not a valid version.
    :return: The highest version string.
    """
    if isinstance(versions, str):
        versions = versions.split(",")
    entries = [str(v).strip() for v in versions]
    if not entries or any(not e for e in entries):
        raise BakeryTemplateError(f"maxVersion requires at least one non-empty version, got: {versions!r}")
    if len(entries) == 1:
        return entries[0]
    best_version: DependencyVersion | None = None
    best_entry = entries[0]
    for entry in entries:
        try:
            parsed = DependencyVersion(entry)
        except InvalidVersion as e:
            raise BakeryTemplateError(f"maxVersion could not parse version '{entry}': {e}") from e
        if best_version is None or parsed >= best_version:
            best_version, best_entry = parsed, entry
    return best_entry


def jinja2_env(**kwargs) -> jinja2.Environment:
    """Creates a Jinja2 environment with custom filters

    :param kwargs: Additional keyword arguments to pass to the Jinja2 Environment constructor.
    :return: A Jinja2 Environment instance with custom filters added.
    """
    env = jinja2.Environment(**kwargs)
    env.filters["tagSafe"] = lambda s: re.sub(REGEX_IMAGE_TAG_SUFFIX_ALLOWED_CHARACTERS_PATTERN, "-", s).strip("-._")
    env.filters["stripMetadata"] = lambda s: re.sub(r"[+-](?=[^+-]*$).*", "", s)
    env.filters["stripPatch"] = strip_patch
    env.filters["condense"] = lambda s: re.sub(r"[ .-]", "", s)
    env.filters["regexReplace"] = lambda s, find, replace: re.sub(find, replace, s)
    env.filters["quote"] = lambda s: '"' + s + '"'
    env.filters["maxVersion"] = max_version
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


def normalize_rendered_output(text: str) -> str:
    """Normalize rendered template output to match common pre-commit hook fixes.

    Strips trailing spaces and tabs from each line and ensures the result
    ends with exactly one newline (or stays empty if it was empty). This
    matches the output of the `trailing-whitespace` and `end-of-file-fixer`
    pre-commit hooks, so files written by bakery's renderer don't fail
    those hooks in consuming repositories.

    :param text: The rendered template text to normalize.
    :return: The normalized text.
    """
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    if text:
        text = text.rstrip("\n") + "\n"
    return text
