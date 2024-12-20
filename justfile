#!/usr/bin/env just --justfile

################
# Variables
CWD := justfile_dir()

################
# Default command, must be first in the file
[private]
_default:
    just -l

################
# Setup commands

# Set up local dev environment
setup:
    just _setup-pre-commit
    just _setup-poetry

[private]
_python-executable executable:
    echo -e "\n{{ executable }} not found, please install it using one of\n  pipx install {{ executable }}\n  uvx install {{ executable }}\n"
    exit 1

[private]
_setup-pre-commit:
    pre-commit --version || just _python-executable pre-commit
    pre-commit install --install-hooks

[private]
_setup-poetry:
    poetry --version || just _python-executable poetry

################
# Omnibus commands for all projects

# Install all sub-projects in the repository
install:
    just --justfile posit-bakery/justfile install

# Test all sub-projects in the repository
test:
    just --justfile posit-bakery/justfile test

# Build all sub-projects in the repository
build:
    just --justfile posit-bakery/justfile build
