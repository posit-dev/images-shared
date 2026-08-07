#!/usr/bin/env just --justfile

# required by the `oven` recipe below: passes *ARGS to the recipe's shell as
# real positional parameters ("$@") instead of `just`'s default plain-text
# substitution. Plain {{ ARGS }} joins arguments with unquoted spaces, so a
# single argument containing a space (e.g. `bash -lc "docker ps"`) silently
# splits into two words before any shell sees it — this passed CI-looking
# (exit 0) but silently wrong output through two separate rounds before it
# was caught. Do not revert this to {{ ARGS }}.
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

# Multi-arch (linux/arm64 from amd64, or vice versa) needs one-time host
# QEMU setup — see CONTRIBUTING.md.

# Build (if stale) and drop into the oven with sibling repos mounted
#
# images-shared is worked on via git worktrees, so {{ CWD }} is never the
# main checkout — sibling product repos live next to *that*, not next to a
# worktree path, and a worktree's own .git is a pointer file into the main
# checkout's real .git. Resolving the mount root via git-common-dir + two
# dirnames gets the right directory either way (plain checkout or
# worktree). It must be mounted at an identical host/container path because
# dgoss and `bakery build` construct bind-mount arguments that only the
# *host* daemon (on the other end of the socket) ever resolves.
oven *ARGS: oven-build
    git_common_dir="$(git -C "{{ CWD }}" rev-parse --path-format=absolute --git-common-dir)"; \
    : "${git_common_dir:?failed to resolve git-common-dir for this checkout}"; \
    mount_root="$(dirname "$(dirname "$git_common_dir")")"; \
    docker_gid="$(stat -c '%g' /var/run/docker.sock 2>/dev/null || stat -f '%g' /var/run/docker.sock)"; \
    : "${docker_gid:?failed to read the group ID of /var/run/docker.sock}"; \
    mkdir -p "$HOME/.cache/bakery-oven/home" || exit 1; \
    docker run --rm -i $(test -t 0 && echo -t) \
        --user "$(id -u):$(id -g)" \
        --group-add "$docker_gid" \
        --network host \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v "$mount_root:$mount_root" \
        -v "$HOME/.cache/bakery-oven:/opt/oven/state" \
        -e BAKERY_REPO_PATH="{{ CWD }}" \
        -e DGOSS_TEMP_DIR="$mount_root" \
        -w "{{ CWD }}" \
        bakery-oven "$@"
