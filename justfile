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
# Oven commands (local build/test/validate/scan environment)

# Build the bakery-oven image
oven-build:
    docker build -t bakery-oven -f {{ CWD }}/oven/Containerfile {{ CWD }}/oven

# Build (if stale) and drop into the oven with sibling repos mounted
oven *ARGS: oven-build
    docker run --rm -i $(test -t 1 && echo -t) \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v "$(dirname {{ CWD }}):$(dirname {{ CWD }})" \
        -e BAKERY_REPO_PATH={{ CWD }} \
        -w {{ CWD }} \
        bakery-oven {{ ARGS }}
