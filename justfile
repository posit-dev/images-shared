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
    echo -e "\n{{ executable }} not found, please install it with\n  uv tool install {{ executable }}\n"
    exit 1

[private]
_setup-pre-commit:
    pre-commit --version || just _python-executable pre-commit
    pre-commit install --install-hooks

################
# Linting

# Check links in markdown with lychee
check-links:
    docker run --rm -w /input -v "{{ CWD }}":/input:ro \
      lycheeverse/lychee --no-progress '**/*.md'
