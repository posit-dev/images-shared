#!/usr/bin/env just --justfile

################
# Variables
CWD := justfile_directory()

################
# Default command, must be first in the file
[private]
_default:
    just --list --unsorted

################
# Setup commands

# Set up local dev environment
setup:
    just _setup-pre-commit

[private]
_python-executable executable:
    echo -e "\n{{ executable }} not found, please install it using one of\n  pipx install {{ executable }}\n  uvx install {{ executable }}\n"
    exit 1

[private]
_setup-pre-commit:
    pre-commit --version || just _python-executable pre-commit
    pre-commit install --install-hooks
