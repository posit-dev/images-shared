import re

# To standardize our images, we will only allow a subset of the regexes
# https://github.com/containers/image/blob/main/docker/reference/regexp.go

# Only allow lowercase letters, number, hyphens, underscores, and periods
# Do not use raw strings here to avoid escaping (e.g. r"{{.+?}}")
RE_TAG_STR: re.Pattern = re.compile("^[a-z0-9][a-z0-9-_.]+$")

# Allow for Jinja2 template in tags
RE_TAG_JINJA: re.Pattern = re.compile("^([a-z0-9-_.]|(?P<jinja>{{.+?}}))+$")
RE_FIRST_CHAR: re.Pattern = re.compile("^[a-z0-9{]")


def is_tag_valid_str(tag: str) -> bool:
    """Check if a tag is a valid string

    :param tag: Tag to check
    """
    return bool(len(tag) <= 128 and RE_TAG_STR.match(tag))


def is_tag_valid_jinja(tag: str) -> bool:
    """Check if tag contains valid Jinja2

    Since the regex also matches valid string tags, we need to check whether
    the match actually includes Jinja2.

    :param tag: Tag to check
    """
    j2 = RE_TAG_JINJA.match(tag)
    if not j2:
        return False

    first_char = RE_FIRST_CHAR.match(tag)
    return bool(j2.groupdict().get("jinja") and first_char)


def is_tag_valid(tag: str) -> bool:
    """Check if tag is valid

    :param tag: Tag to check
    """
    return is_tag_valid_str(tag) or is_tag_valid_jinja(tag)
