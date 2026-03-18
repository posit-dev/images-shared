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
pipx install 'poetry>=2'
just setup

# Install the project locally
just install

# Run tests (skipping slow tests)
just test

# Run all tests
just test-all
```

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

## Key Commands

Commands support aliases for convenience:
- `build` → `b`, `bake`
- `create` → `c`, `new`
- `run` → `r`
- `update` → `u`, `up`
- `remove` → `rm`

### Creating a New Project

```bash
# Initialize a new bakery project
bakery create project
```

### Creating a New Image

```bash
# Create a new image template
bakery create image <image-name>
```

This creates:
- A directory for the image with the specified name
- A `template/` subdirectory with Jinja2 templates
- Default templates for Containerfile, package list, and tests
- Updates the `bakery.yaml` file with the new image

### Creating a New Image Version

```bash
# Create a new version of an existing image
bakery create version <image-name> <version>
```

This creates:
- A versioned directory under the image directory
- Renders templates with version-specific values
- Updates `bakery.yaml` with the new version

### Building Images

```bash
# Preview the bake plan without building
bakery build --plan

# Build all images in the project
bakery build

# Build a specific image
bakery build --image-name <image-name>

# Build a specific version
bakery build --image-version <version>

# Build a specific variant
bakery build --image-variant <variant>

# Build a specific OS
bakery build --image-os <os>
```

The build command supports two strategies:
- `--strategy bake` (default): Uses Docker Buildx Bake for parallel building
- `--strategy build`: Sequential builds with Docker, Podman, or nerdctl

### Running Tests

```bash
# Run dgoss tests against all images
bakery run dgoss

# Run dgoss tests against a specific image
bakery run dgoss --image-name <image-name>
```

### Updating Files and Versions

```bash
# Re-render templates to version files
bakery update files

# Re-render templates for a specific image/version
bakery update files --image-name <image-name> --image-version <version>

# Patch an existing version to a new version (preserves config)
bakery update version patch <image-name> <old-version> <new-version>
```

### Removing Images and Versions

```bash
# Remove an entire image and its configuration
bakery remove image <image-name>

# Remove a specific version from an image
bakery remove version <image-name> <version>
```

### CI/CD Operations

```bash
# Generate a JSON matrix for CI workflows
bakery ci matrix

# Generate matrix for a specific image
bakery ci matrix <image-name>

# Merge multi-platform build metadata files
bakery ci merge <metadata-file1> <metadata-file2> ...
```

### Registry Cleanup

```bash
# Clean dangling build caches in GHCR
bakery clean cache-registry <registry>

# Clean temporary images in GHCR
bakery clean temp-registry <registry>

# Dry run to preview what would be deleted
bakery clean cache-registry <registry> --dry-run
```

### Creating a Matrix-Based Image

```bash
# Create a matrix configuration for multi-dimensional builds
bakery create matrix <image-name> \
  --dependency-constraint '{"dependency": "R", "latest": true, "count": 2}' \
  --dependency-constraint '{"dependency": "Python", "latest": true, "count": 2}'
```

## Architecture Concepts

### Project Structure

```
.
├── bakery.yaml          # Main configuration file
├── image-name/          # Directory for each image
│   ├── 2024.12.0/       # Directory for each version
│   ├── 2025.01.0/
│   └── template/        # Jinja2 templates for the image
└── another-image/
    ├── 2025.02.0/
    └── template/
```

### Configuration Schema

The `bakery.yaml` file defines:
- Repository metadata
- Registry configuration
- Image definitions with:
- Variants (e.g., Standard, Minimal)
- Versions with OS support
- Dependency constraints

### Image Templating System

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

## Build Process

1. `bakery build` reads the `bakery.yaml` configuration
2. Generates a Docker Buildx Bake plan (`.docker-bake.json`)
3. Invokes Docker Buildx to build images in parallel
4. Optionally loads images into Docker or pushes to registries

## Testing Process

1. `bakery run dgoss` finds images to test based on configuration
2. Executes dgoss tests against each image with appropriate test files
3. Collects and reports test results

## Image Tagging

Bakery automatically applies tag patterns based on:
- Version (`<version>-<os>-<type>`)
- Latest version markers (`<os>-<type>`, `latest`)
- Primary OS and variant combinations

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

### Common CI failure modes

- **Python version not in UV** — UV's release metadata may lag behind new CPython releases. Check UV's [download-metadata.json](https://raw.githubusercontent.com/astral-sh/uv/refs/heads/main/crates/uv-python/download-metadata.json).
- **Stale layer cache** — builds use `--cache-registry ghcr.io/posit-dev`. If a cached layer has outdated packages, the `clean.yml` workflow removes caches older than 14 days, but you may need to manually bust the cache.
- **Registry auth failures** — Docker Hub requires `DOCKER_HUB_ACCESS_TOKEN` secret; ECR requires AWS OIDC (`id-token: write` permission + `AWS_ROLE` secret).
- **ARM64 runner unavailable** — native builds use `ubuntu-24.04-arm64-4-core` runners which may have capacity limits.

## Advanced Usage

### Adding Dependencies

Define dependency constraints in the `bakery.yaml` file:

```yaml
dependencyConstraints:
  - dependency: python
    constraint:
      latest: true
      count: 2
  - dependency: R
    constraint:
      max: "4.4"
      count: 1
```

### Custom Templates

Create custom Jinja2 templates in the image's `template/` directory with the `.jinja2` extension.

### Custom Tag Patterns

Define custom tag patterns in the `bakery.yaml` file:

```yaml
tagPatterns:
  - patterns: ["{{ Version }}-{{ OS }}"]
    only:
      - "primaryVariant"
```

### Image Matrices

For images that need multiple dependency combinations (e.g., different R and Python versions), use image matrices instead of individual versions:

```yaml
images:
  - name: my-image
    matrix:
      namePattern: "r{{ R }}-py{{ Python }}"
      subpath: matrix
      dependencies:
        - dependency: R
          versions: ["4.3.3", "4.4.1"]
        - dependency: Python
          versions: ["3.11", "3.12"]
```

This generates versions for each combination of dependencies.

### Multi-Platform Builds

For CI workflows using native builders (instead of QEMU emulation):

1. Build for each platform separately with `--temp-registry`:
   ```bash
   bakery build --strategy build --platform linux/amd64 --metadata-file amd64.json --temp-registry ghcr.io/org
   bakery build --strategy build --platform linux/arm64 --metadata-file arm64.json --temp-registry ghcr.io/org
   ```

2. Merge the metadata files into multi-platform manifests:
   ```bash
   bakery ci merge amd64.json arm64.json
   ```
