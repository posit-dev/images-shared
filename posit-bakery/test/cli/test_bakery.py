import re

from pytest_bdd import scenarios, then

scenarios(
    "cli/bakery.feature",
)


VERSION_OUTPUT_REGEX = re.compile(
    r"^Posit Bakery v(\d+!)?(\d+)(\.\d+)+([.\-_])?"
    r"((a(lpha)?|b(eta)?|c|r(c|ev)?|pre(view)?)\d*)?(\.?(post|dev)\d*)?$"
)


@then("the version is shown")
def check_version(bakery_command):
    assert VERSION_OUTPUT_REGEX.match(bakery_command.result.stdout) is not None
