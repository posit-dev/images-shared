#!/usr/bin/env just --justfile

set positional-arguments := true

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
    docker build -t bakery-oven -f "{{ CWD }}/oven/Containerfile" "{{ CWD }}/oven"

# Build (if stale) and drop into the oven with sibling repos mounted
oven *ARGS: oven-build
    git_common_dir="$(git -C "{{ CWD }}" rev-parse --path-format=absolute --git-common-dir)"; \
    : "${git_common_dir:?failed to resolve this checkout's git-common-dir}"; \
    mount_root="$(dirname "$(dirname "$git_common_dir")")"; \
    docker_gid="$(stat -c '%g' /var/run/docker.sock 2>/dev/null || stat -f '%g' /var/run/docker.sock)"; \
    : "${docker_gid:?failed to read the group ID of /var/run/docker.sock}"; \
    mkdir -p "$HOME/.cache/bakery-oven"; \
    docker run --rm -i $(test -t 0 && echo -t) \
        --user "$(id -u):$(id -g)" \
        --group-add "$docker_gid" \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v "$mount_root:$mount_root" \
        -v "$HOME/.cache/bakery-oven:/opt/oven/state" \
        -e BAKERY_REPO_PATH="{{ CWD }}" \
        -w "{{ CWD }}" \
        bakery-oven "$@"
