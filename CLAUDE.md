# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Posit Bakery is a command-line tool for building, testing, and managing containerized images. It provides a structured approach to create, build, and test Docker images with variant support (e.g., Standard vs Minimal), version management, OS variants, and dependency constraints.

The tool uses a YAML configuration file (`bakery.yaml`) and Jinja2 templates to define image builds, with support for parallel building via Docker Buildx Bake.

## Sibling Repositories

This project is part of a multi-repo ecosystem for Posit container images. Sibling repos
are configured as additional directories (see `.claude/settings.json`). **When making
changes that affect bakery config, templates, macros, or CLI behavior, read the CLAUDE.md
and `bakery.yaml` in each affected sibling repo before making changes there.**

- `../images/` - Meta repository with documentation, design principles, and links across all image repos. No `bakery.yaml`; no buildable images.
- `../images-connect/` - Posit Connect images: `connect` (Standard/Minimal variants), `connect-content` (matrix of R x Python), `connect-content-init`. Uses dependency constraints for R, Python, and Quarto.
- `../images-package-manager/` - Posit Package Manager image: `package-manager` (Standard/Minimal variants). Supports multi-platform builds (amd64/arm64).
- `../images-workbench/` - Posit Workbench images: `workbench` (Standard/Minimal variants), `workbench-session` (R x Python matrix), `workbench-session-init`. Uses Go for session init builds.
- `../images-examples/` - Examples for using and extending Posit container images. Contains both Bakery-based examples (`bakery/`) and Containerfile-based extension examples (`extending/`). Has its own CLAUDE.md.
- `../helm/` - Helm charts for Posit products: Connect, Workbench, Package Manager, and Chronicle.

All product image repos (`images-connect`, `images-package-manager`, `images-workbench`)
share the same structure: a `bakery.yaml` at the root, image directories with `template/`
subdirectories containing Jinja2 templates, and rendered version directories. They all use
`posit-bakery` (from this repo) as their build tool and share the same CI workflows.

### Worktrees for Cross-Repo Changes

When making changes across repositories, use worktrees to isolate work from `main`. Multiple
sessions may be running concurrently, so never work directly on `main` in any repo.

- **Primary repo:** Use `EnterWorktree` with a descriptive name.
- **Sibling repos:** Create worktrees via `git worktree add` before making changes. Store
  them in `.claude/worktrees/<name>` within each repo (matching the `EnterWorktree` convention).

```bash
# Create a worktree in a sibling repo
git -C ../images-connect worktree add .claude/worktrees/<name> -b <branch-name>
```

Read and write files via the worktree path (e.g., `../images-connect/.claude/worktrees/<name>/`)
instead of the repo root. Clean up when finished:

```bash
git -C ../images-connect worktree remove .claude/worktrees/<name>
```

> **Note:** The `additionalDirectories` in `.claude/settings.json` point to the sibling repo
> roots, not to worktree paths. File reads and writes via those directories will access the
> repo root (typically on `main`). Always use the full worktree path when reading or writing
> files in a sibling worktree.

> **Bash commands:** Use `git -C <path>` instead of `cd <path> && git ...` for sibling repo
> operations. The sandbox restricts `cd` to parent/sibling directories, but `git -C` runs
> git from a target directory without changing the working directory.

## Posit Product Naming

| Current Name | Legacy Name | ENV Prefix | Legacy Prefix | Helm Chart |
|---|---|---|---|---|
| Posit Connect | RStudio Connect | `PCT_` | `RSC_` | `rstudio-connect` |
| Posit Workbench | RStudio Workbench | `PWB_` | `RSW_`, `RSP_` | `rstudio-workbench` |
| Posit Package Manager | RStudio Package Manager | `PPM_` | `RSPM_` | `rstudio-pm` |

Legacy env var prefixes are supported via fallback in each product's `startup.sh`.
When adding or modifying env vars, always use the current prefix and maintain backward
compatibility with the legacy prefix.

## Development Environment Setup

Run these commands from the `posit-bakery/` directory:

```bash
# Install dependencies
just setup

# Install the project locally
just install

# Run tests (skipping slow tests)
just test

# Run all tests
just test-all
```

**Always use `uv` instead of `python`** for invoking Python commands, running scripts, or
executing tools like `pytest`. For example:

- `uv run pytest` instead of `python -m pytest` or `pytest`
- `uv run python script.py` instead of `python script.py`
- `uv run bakery ...` instead of `bakery ...` (when running outside of `just`)

This ensures the correct virtual environment and dependencies are used automatically
without requiring manual activation.

## Repository Structure

This is a monorepo containing multiple projects:

- `posit-bakery/` - The main Posit Bakery CLI tool
  - `posit_bakery/` - Core Python package
    - `cli/` - Command-line interface implementation
    - `config/` - Configuration handling and validation
      - `dependencies/` - Dependency management (Python, R, Quarto versions)
      - `image/` - Image configuration models (variants, versions, matrices)
      - `templating/` - Jinja2 template definitions and macros
      - `tools/` - Tool configurations (goss)
    - `image/` - Image building and management
      - `bake/` - Docker Buildx Bake integration
      - `goss/` - Goss testing integration
    - `registry_management/` - Registry APIs (DockerHub, GHCR)
    - `services/` - Registry container services
  - `test/` - Test suite
- `setup-bakery/` - Bakery setup utilities
- `setup-goss/` - Goss testing setup utilities
- `presentations/` - Project presentations

## Bakery CLI

Run `bakery --help` and `bakery <command> --help` for full command reference.
Commands have aliases: `build`/`b`, `create`/`c`, `run`/`r`, `update`/`u`, `remove`/`rm`.

Key commands for product repos: `bakery build`, `bakery build --plan`, `bakery run dgoss`,
`bakery update files`, `bakery create version`, `bakery ci matrix`.

## Image Templating System

**Always edit Jinja2 templates in `template/`, never the rendered files in version directories.**
After changing templates, re-render with `bakery update files`.

Bakery uses Jinja2 for templating with shared macros in `posit_bakery/config/templating/macros/`:

| Macro | Purpose |
|---|---|
| `apt.j2` | APT package setup, install, and cleanup |
| `dnf.j2` | DNF package management (RHEL) |
| `python.j2` | Python installation via UV multi-stage builds |
| `r.j2` | R installation via rstd.io/r-install |
| `quarto.j2` | Quarto and TinyTeX installation |
| `goss.j2` | Goss test helpers |
| `wait-for-it.j2` | wait-for-it.sh script installation |

Key Python/UV pattern — multi-stage build:
```jinja2
{{ python.build_stage(Dependencies.python) }}  {# Separate UV builder stage #}
FROM base-image
{{ python.copy_from_build_stage() }}           {# Copy /opt/python from builder #}
```

UV installs to `cpython-{version}-linux-{arch}/`; macros normalize paths to `/opt/python/{version}/`.

Template variables available:
- `Image.Version`, `Image.Variant`, `Image.OS` (with `.Name`, `.Family`, `.Version`, `.Codename`), `Image.IsDevelopmentVersion`
- `Path.Base`, `Path.Image`, `Path.Version`
- `Dependencies.python`, `Dependencies.R`, `Dependencies.quarto` (lists of version strings)

Custom Jinja2 filters: `tagSafe`, `stripMetadata`, `condense`, `regexReplace`, `quote`, `split`

## Python Coding Conventions

### Imports

Prefer file-level (top-of-file) imports over locally-scoped imports. Local imports should
only be used when there is a legitimate reason, such as:

- Avoiding a circular import
- Avoiding importing a large or optional dependency unless it is actually needed
- Deferring an import for performance in a rarely-used code path

When a local import is used, add a comment explaining why it is local rather than at the
top of the file.

## CI/CD Architecture

This repo provides shared reusable GitHub Actions workflows that all product image repos call:

| Workflow | Purpose |
|---|---|
| `bakery-build-native.yml` | Native multi-platform builds (amd64/arm64 on separate runners), merges with `bakery ci merge` |
| `bakery-build.yml` | QEMU-based builds (single runner, slower but simpler) |
| `clean.yml` | Registry cleanup (dangling caches, temporary images) |

### How product repos use these workflows

Each product repo has 2-3 workflow files that call the shared workflows:

- **production.yml** — weekly + PR + push to main. Builds release versions, pushes to Docker Hub + GHCR.
- **development.yml** — daily/hourly + PR + push to main. Builds dev stream versions, pushes to GHCR/ECR.
- **content.yml / session.yml** — weekly + PR + push to main. Builds matrix images (R x Python combinations).

### Build pipeline flow

1. `bakery ci matrix` generates a JSON matrix of image/version/platform combinations
2. Each combination builds on a separate runner (`bakery build --strategy build --push`)
3. Build artifacts push to a temp registry (`--temp-registry ghcr.io/posit-dev`)
4. `bakery ci merge` creates multi-platform manifests and pushes final tags

### Debugging CI failures

Use the `gh` CLI to inspect workflow runs without leaving the terminal:

```bash
# List recent workflow runs
gh run list -R posit-dev/images-connect

# View a specific run (shows jobs and status)
gh run view <run-id> -R posit-dev/images-connect

# View logs for a failed job
gh run view <run-id> -R posit-dev/images-connect --log-failed
```

### Common CI failure modes

- **Python version not in UV** — When a new CPython minor version is released, UV's managed Python list may not include it yet. The `python.build_stage()` macro calls `uv python install` which fails if the version isn't available. Check UV's [download-metadata.json](https://raw.githubusercontent.com/astral-sh/uv/refs/heads/main/crates/uv-python/download-metadata.json) to confirm availability. Fix: wait for UV to add the version, or pin to an available version in `bakery.yaml`.
- **Stale UV base image cache** — The Python build stage uses `ghcr.io/astral-sh/uv:debian-slim` as its base image. Docker layer caching may preserve an older UV version that doesn't know about newer Python releases. Even if UV upstream supports a Python version, a cached builder layer may not. Fix: the `clean.yml` workflow removes caches older than 14 days, but you can force a fresh build by clearing the cache registry (`bakery clean cache-registry ghcr.io/posit-dev`).
- **Registry auth failures** — Docker Hub requires `DOCKER_HUB_ACCESS_TOKEN` secret; ECR requires AWS OIDC (`id-token: write` permission + `AWS_ROLE` secret).
- **ARM64 runner unavailable** — Native builds use `ubuntu-24.04-arm64-4-core` runners which may have capacity limits.
- **Dispatched version doesn't match bakery** — Product repos dispatch with raw git-describe versions (e.g. `v2026.03.0-473-g072bb6fd1f`). Bakery normalizes these to semver-with-metadata (e.g. `2026.04.0-dev+473-g072bb6fd1f`). The shared workflows strip a leading `v` automatically, but other format differences (edition, `-dev` qualifier, `+` separator) mean `--image-version` requires the version string bakery knows, not the raw product version. If the matrix is empty after filtering, `bakery ci matrix` exits non-zero.
