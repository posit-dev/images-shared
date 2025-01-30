# conftest.py loads this file via pytest_plugins
from pytest_bdd import given, when, then, parsers


# Construct the bakery command and all arguments
@given("I call bakery")
def bare_command(bakery_command):
    bakery_command._subcommand = None


@given(parsers.parse('I call bakery "{command}"'))
def sub_command(bakery_command, command):
    bakery_command._subcommand = command


@given("with the basic context")
def basic_context(bakery_command, basic_context):
    bakery_command.add_args(["--context", str(basic_context)])


@given("with a temp basic context")
def tmp_context(bakery_command, basic_tmpcontext):
    bakery_command.add_args(["--context", str(basic_tmpcontext)])


@given("with the arguments:")
def add_args_table(bakery_command, datatable):
    for row in datatable:
        bakery_command.add_args(row)


# Run the command
@when("I execute the command")
def run(bakery_command):
    bakery_command.run()


# Check the results of the command
@then("The command succeeds")
def check_success(bakery_command):
    assert bakery_command.result.exit_code == 0


@then("The command fails")
def check_failure(bakery_command):
    assert bakery_command.result.exit_code != 0


@then("usage is shown")
def check_usage(bakery_command):
    # TODO: Make this check more robust, with options for specific output
    assert "Usage:" in bakery_command.result.stdout


@then("an error message is shown")
def check_error(bakery_command):
    assert "Error" in bakery_command.result.stdout


@then("the output includes:")
def check_stdout(bakery_command, datatable):
    for row in datatable:
        assert row[0] in bakery_command.result.stdout
